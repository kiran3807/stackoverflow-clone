import json
import os
from typing import List, Optional, Dict, Any, cast, Literal
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, insert, delete
from .db.models import User, Question as DBQuestion, Answer as DBAnswer, Tag, Vote, AnalyticsLog
from .models import QuestionSummary, PaginatedResponse, SearchRequest, SearchResponse
import math
from datetime import datetime
from sqlalchemy import func
from .db.models import question_tags
from .models import QuestionCreate, AnswerCreate, TagCreate, UserCreate
from pydantic import BaseModel

class DbUpdatePayload(BaseModel):
    text: str  # Natural language description of the update
    table_name: str
    update_type: Literal["insert", "update", "delete"]
    values: Dict[str, Any]

class DataService:
    def __init__(self, db: Session):
        self.db = db
    
    def _log_db_update(self, text: str, table_name: str, update_type: Literal["insert", "update", "delete"], values: Dict[str, Any], user_id: Optional[int] = None):
        """Helper method to log database updates to AnalyticsLog"""
        try:
            payload = DbUpdatePayload(
                text=text,
                table_name=table_name,
                update_type=update_type,
                values=values
            )
            
            log_entry = AnalyticsLog(
                session_id=f"data_service_{datetime.utcnow().timestamp()}",
                event_type="update_db",
                event_data=payload.model_dump(),
                timestamp=datetime.utcnow(),
                user_id=user_id
            )
            
            self.db.add(log_entry)
            self.db.flush()  # Ensure it's written to the current transaction
            
        except Exception as e:
            # Log the error but don't fail the main operation
            pass  # Silent failure to avoid disrupting main operations
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_users(self, page: int = 1, limit: int = 20, search: Optional[str] = None) -> PaginatedResponse:
        """Get paginated list of users with optional search"""
        query = self.db.query(User)
        
        if search:
            query = query.filter(
                (User.name.ilike(f"%{search}%")) |
                (User.location.ilike(f"%{search}%"))
            )
        
        total = query.count()
        users = query.offset((page - 1) * limit).limit(limit).all()
        
        return PaginatedResponse(
            items=users,
            total=total,
            page=page,
            limit=limit
        )
    
    def get_question_by_id(self, question_id: int) -> Optional[Dict]:
        """Get question by ID with answers"""
        question = self.db.query(DBQuestion).filter(DBQuestion.id == question_id).first()
        if question:
            # Add answers to question
            question.answers = self.get_answers(question_id=question_id)
            return question
        return None
    
    def get_questions(self, skip: int = 0, limit: int = 10, sort: str = "newest") -> List[DBQuestion]:
        """Get a list of questions with pagination"""
        query = self.db.query(DBQuestion).options(
            joinedload(DBQuestion.author),
            joinedload(DBQuestion.tags),
            joinedload(DBQuestion.answers)
        )
        
        if sort == "newest":
            query = query.order_by(DBQuestion.created_at.desc())
        elif sort == "votes":
            query = query.order_by(DBQuestion.votes.desc())
        elif sort == "active":
            query = query.order_by(DBQuestion.updated_at.desc())
        
        return query.offset(skip).limit(limit).all()
    
    def get_total_questions(self) -> int:
        """Get total number of questions"""
        return self.db.query(DBQuestion).count()
    
    def get_questions_by_user(self, user_id: int, page: int = 1, limit: int = 15) -> PaginatedResponse:
        """Get questions by user with pagination"""
        query = self.db.query(DBQuestion).options(
            joinedload(DBQuestion.author),
            joinedload(DBQuestion.tags),
            joinedload(DBQuestion.answers)
        ).filter(DBQuestion.author_id == user_id)
        total = query.count()
        questions = query.offset((page - 1) * limit).limit(limit).all()
        
        return PaginatedResponse(
            items=questions,
            total=total,
            page=page,
            limit=limit
        )
    
    def get_answers_by_user(self, user_id: int, page: int = 1, limit: int = 15) -> PaginatedResponse:
        """Get answers by user with pagination"""
        query = self.db.query(DBAnswer).filter(DBAnswer.author_id == user_id)
        total = query.count()
        answers = query.offset((page - 1) * limit).limit(limit).all()
        
        return PaginatedResponse(
            items=answers,
            total=total,
            page=page,
            limit=limit
        )
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user statistics"""
        user_questions = self.db.query(DBQuestion).filter(DBQuestion.author_id == user_id).count()
        user_answers = self.db.query(DBAnswer).filter(DBAnswer.author_id == user_id).count()
        
        # Calculate total votes received
        question_votes = self.db.query(DBQuestion).filter(DBQuestion.author_id == user_id).with_entities(func.sum(DBQuestion.votes)).scalar() or 0
        answer_votes = self.db.query(DBAnswer).filter(DBAnswer.author_id == user_id).with_entities(func.sum(DBAnswer.votes)).scalar() or 0
        
        return {
            "questions_count": user_questions,
            "answers_count": user_answers,
            "total_votes": question_votes + answer_votes,
            "question_votes": question_votes,
            "answer_votes": answer_votes
        }
    
    def get_answers_by_question(self, question_id: int):
        """Get all answers for a question"""
        return self.db.query(DBAnswer).filter(DBAnswer.question_id == question_id).all()
    
    def get_tag_by_name(self, tag_name: str) -> Optional[Tag]:
        """Get tag by name"""
        return self.db.query(Tag).filter(Tag.name.ilike(tag_name)).first()
    
    def get_questions_by_tag(self, tag_name: str, page: int = 1, limit: int = 15, sort: str = "newest") -> PaginatedResponse:
        """Get questions filtered by tag with pagination"""
        tag = self.get_tag_by_name(tag_name)
        if not tag:
            return PaginatedResponse(items=[], total=0, page=page, limit=limit)
        
        query = self.db.query(DBQuestion).options(
            joinedload(DBQuestion.author),
            joinedload(DBQuestion.tags),
            joinedload(DBQuestion.answers)
        ).filter(DBQuestion.tags.contains([tag_name]))
        
        if sort == "newest":
            query = query.order_by(DBQuestion.created_at.desc())
        elif sort == "votes":
            query = query.order_by(DBQuestion.votes.desc())
        elif sort == "active":
            query = query.order_by(DBQuestion.updated_at.desc())
        
        total = query.count()
        questions = query.offset((page - 1) * limit).limit(limit).all()
        
        return PaginatedResponse(
            items=questions,
            total=total,
            page=page,
            limit=limit
        )
    
    def get_popular_tags(self, limit: int = 20) -> List[Tag]:
        """Get most popular tags"""
        return self.db.query(Tag).order_by(Tag.count.desc()).limit(limit).all()
    
    def get_trending_tags(self, limit: int = 10) -> List[Tag]:
        """Get trending tags (for demo, return most popular)"""
        return self.get_popular_tags(limit)
    
    def search_questions(self, query: str, tags: Optional[List[str]] = None, skip: int = 0, limit: int = 20, sort: str = "relevance") -> tuple[List[Dict], int]:
        """Search questions by title or content"""
        search_query = self.db.query(DBQuestion).filter(
            (DBQuestion.title.ilike(f"%{query}%")) | (DBQuestion.body.ilike(f"%{query}%"))
        )
        
        if tags:
            # Join with tags table and filter by tag names
            search_query = search_query.join(DBQuestion.tags).filter(Tag.name.in_(tags))
        
        if sort == "relevance":
            # For now, just sort by newest
            search_query = search_query.order_by(DBQuestion.created_at.desc())
        elif sort == "newest":
            search_query = search_query.order_by(DBQuestion.created_at.desc())
        elif sort == "votes":
            search_query = search_query.order_by(DBQuestion.votes.desc())
        
        total = search_query.count()
        questions = search_query.offset(skip).limit(limit).all()
        
        # Convert to dictionary format
        result = []
        for q in questions:
            result.append({
                "id": q.id,
                "title": q.title,
                "content": q.body,
                "author": q.author,
                "tags": [t.name for t in q.tags],
                "votes": q.votes,
                "views": q.views,
                "answer_count": len(q.answers),
                "asked": q.created_at
            })
        
        return result, total
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        print(f"Searching for user with username: {username}")
        user = self.db.query(User).filter(User.name == username).first()
        print(f"User found: {user is not None}")
        if user:
            print(f"User details - ID: {user.id}, Name: {user.name}, Email: {user.email}")
        return user
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.db.query(User).filter(User.email == email).first()
    
    def create_user(self, name: str, email: str, hashed_password: str) -> User:
        """Create a new user"""
        user = User(
            name=name,
            email=email,
            hashed_password=hashed_password,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            reputation=0,
            is_active=True,
            is_deleted=False,
            last_seen=datetime.utcnow()
        )
        self.db.add(user)
        
        # Log the database update
        self._log_db_update(
            text=f"Created new user '{name}' with email '{email}'",
            table_name="users",
            update_type="insert",
            values={"name": name, "email": email, "reputation": 0, "is_active": True}
        )
        
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def get_question(self, question_id: int) -> Optional[DBQuestion]:
        """Get question by ID"""
        return self.db.query(DBQuestion).filter(DBQuestion.id == question_id).first()
    
    def create_question(self, question: QuestionCreate, author_id: int):
        """Create a new question"""
        from .db.models import Question as DBQuestion, Tag
        
        db_question = DBQuestion(
            title=question.title,
            body=question.body,
            author_id=author_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(db_question)
        
        # Log the database update
        self._log_db_update(
            text=f"Created new question '{question.title}' by user {author_id}",
            table_name="questions",
            update_type="insert",
            values={"title": question.title, "author_id": author_id, "tags": question.tags or []},
            user_id=author_id
        )
        
        self.db.commit()
        self.db.refresh(db_question)
        
        # Process tags
        if question.tags:
            for tag_name in question.tags:
                # Check if tag exists, create if not
                tag = self.db.query(Tag).filter(Tag.name == tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    self.db.add(tag)
                    
                    # Log tag creation
                    self._log_db_update(
                        text=f"Created new tag '{tag_name}' for question '{question.title}'",
                        table_name="tags",
                        update_type="insert",
                        values={"name": tag_name},
                        user_id=author_id
                    )
                    
                    self.db.commit()
                    self.db.refresh(tag)
                
                # Add tag to question via many-to-many relationship
                if tag not in db_question.tags:
                    db_question.tags.append(tag)
                    
                    # Log tag association
                    self._log_db_update(
                        text=f"Associated tag '{tag_name}' with question '{question.title}'",
                        table_name="question_tags",
                        update_type="insert",
                        values={"question_id": db_question.id, "tag_id": tag.id},
                        user_id=author_id
                    )
            
            self.db.commit()
            self.db.refresh(db_question)
        
        return db_question
    
    def get_answers(self, question_id: Optional[int] = None, user_id: Optional[int] = None, page: int = 1, limit: int = 20, sort: str = "votes"):
        """Get answers with optional filtering and pagination"""
        query = self.db.query(DBAnswer)
        
        if question_id is not None:
            query = query.filter(DBAnswer.question_id == question_id)
        
        if user_id is not None:
            query = query.filter(DBAnswer.author_id == user_id)
        
        if sort == "votes":
            query = query.order_by(DBAnswer.votes.desc())
        elif sort == "newest":
            query = query.order_by(DBAnswer.created_at.desc())
        elif sort == "oldest":
            query = query.order_by(DBAnswer.created_at.asc())
        
        # Apply pagination
        offset = (page - 1) * limit
        return query.offset(offset).limit(limit).all()
    
    def create_answer(self, question_id: int, user_id: int, content: str):
        """Create a new answer"""
        db_answer = DBAnswer(
            body=content,
            question_id=question_id,
            author_id=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(db_answer)
        
        # Log the database update
        self._log_db_update(
            text=f"Created new answer for question {question_id} by user {user_id}",
            table_name="answers",
            update_type="insert",
            values={"question_id": question_id, "author_id": user_id, "body_length": len(content)},
            user_id=user_id
        )
        
        self.db.commit()
        self.db.refresh(db_answer)
        return db_answer
    
    def vote_question(self, question_id: int, user_id: int, vote_type: str):
        """Vote on a question - prevents duplicate votes"""
        question = self.get_question(question_id)
        if not question:
            raise ValueError("Question not found")
            
        # Check if user has already voted on this question
        existing_vote = self.db.query(Vote).filter(
            Vote.user_id == user_id,
            Vote.question_id == question_id
        ).first()
        
        if existing_vote:
            # If user is changing their vote
            current_vote_type = cast(str, existing_vote.vote_type)
            if current_vote_type != vote_type:
                # Remove old vote effect and add new vote effect
                old_vote_effect = 1 if current_vote_type == "up" else -1
                new_vote_effect = 1 if vote_type == "up" else -1
                vote_delta = new_vote_effect - old_vote_effect
                
                # Update the vote record
                setattr(existing_vote, 'vote_type', vote_type)
                setattr(existing_vote, 'created_at', datetime.utcnow())
                
                # Log the vote change
                self._log_db_update(
                    text=f"User {user_id} changed vote on question {question_id} from {current_vote_type} to {vote_type}",
                    table_name="votes",
                    update_type="update",
                    values={"question_id": question_id, "user_id": user_id, "old_vote": current_vote_type, "new_vote": vote_type},
                    user_id=user_id
                )
                
                # Update question vote count
                self.db.query(DBQuestion).filter(DBQuestion.id == question_id).update({
                    DBQuestion.votes: DBQuestion.votes + vote_delta
                })
                
                # Log question vote count update
                self._log_db_update(
                    text=f"Updated question {question_id} vote count by {vote_delta} (vote change)",
                    table_name="questions",
                    update_type="update",
                    values={"question_id": question_id, "vote_delta": vote_delta, "reason": "vote_change"},
                    user_id=user_id
                )
            # If user is trying to vote the same way again, do nothing (prevent duplicate)
            else:
                return  # No change needed
        else:
            # Create new vote
            new_vote = Vote(
                user_id=user_id,
                question_id=question_id,
                vote_type=vote_type
            )
            self.db.add(new_vote)
            
            # Log new vote
            self._log_db_update(
                text=f"User {user_id} voted {vote_type} on question {question_id}",
                table_name="votes",
                update_type="insert",
                values={"question_id": question_id, "user_id": user_id, "vote_type": vote_type},
                user_id=user_id
            )
            
            # Update question vote count
            vote_delta = 1 if vote_type == "up" else -1
            self.db.query(DBQuestion).filter(DBQuestion.id == question_id).update({
                DBQuestion.votes: DBQuestion.votes + vote_delta
            })
            
            # Log question vote count update
            self._log_db_update(
                text=f"Updated question {question_id} vote count by {vote_delta} (new {vote_type}vote)",
                table_name="questions",
                update_type="update",
                values={"question_id": question_id, "vote_delta": vote_delta, "reason": "new_vote"},
                user_id=user_id
            )
        
        self.db.commit()
    
    def vote_answer(self, answer_id: int, user_id: int, vote_type: str):
        """Vote on an answer - prevents duplicate votes"""
        answer = self.db.query(DBAnswer).filter(DBAnswer.id == answer_id).first()
        if not answer:
            raise ValueError("Answer not found")
            
        # Check if user has already voted on this answer
        existing_vote = self.db.query(Vote).filter(
            Vote.user_id == user_id,
            Vote.answer_id == answer_id
        ).first()
        
        if existing_vote:
            # If user is changing their vote
            current_vote_type = cast(str, existing_vote.vote_type)
            if current_vote_type != vote_type:
                # Remove old vote effect and add new vote effect
                old_vote_effect = 1 if current_vote_type == "up" else -1
                new_vote_effect = 1 if vote_type == "up" else -1
                vote_delta = new_vote_effect - old_vote_effect
                
                # Update the vote record
                setattr(existing_vote, 'vote_type', vote_type)
                setattr(existing_vote, 'created_at', datetime.utcnow())
                
                # Log the vote change
                self._log_db_update(
                    text=f"User {user_id} changed vote on answer {answer_id} from {current_vote_type} to {vote_type}",
                    table_name="votes",
                    update_type="update",
                    values={"answer_id": answer_id, "user_id": user_id, "old_vote": current_vote_type, "new_vote": vote_type},
                    user_id=user_id
                )
                
                # Update answer vote count
                self.db.query(DBAnswer).filter(DBAnswer.id == answer_id).update({
                    DBAnswer.votes: DBAnswer.votes + vote_delta
                })
                
                # Log answer vote count update
                self._log_db_update(
                    text=f"Updated answer {answer_id} vote count by {vote_delta} (vote change)",
                    table_name="answers",
                    update_type="update",
                    values={"answer_id": answer_id, "vote_delta": vote_delta, "reason": "vote_change"},
                    user_id=user_id
                )
            # If user is trying to vote the same way again, do nothing (prevent duplicate)
            else:
                return  # No change needed
        else:
            # Create new vote
            new_vote = Vote(
                user_id=user_id,
                answer_id=answer_id,
                vote_type=vote_type
            )
            self.db.add(new_vote)
            
            # Log new vote
            self._log_db_update(
                text=f"User {user_id} voted {vote_type} on answer {answer_id}",
                table_name="votes",
                update_type="insert",
                values={"answer_id": answer_id, "user_id": user_id, "vote_type": vote_type},
                user_id=user_id
            )
            
            # Update answer vote count
            vote_delta = 1 if vote_type == "up" else -1
            self.db.query(DBAnswer).filter(DBAnswer.id == answer_id).update({
                DBAnswer.votes: DBAnswer.votes + vote_delta
            })
            
            # Log answer vote count update
            self._log_db_update(
                text=f"Updated answer {answer_id} vote count by {vote_delta} (new {vote_type}vote)",
                table_name="answers",
                update_type="update",
                values={"answer_id": answer_id, "vote_delta": vote_delta, "reason": "new_vote"},
                user_id=user_id
            )
        
        self.db.commit()
    
    def increment_question_views(self, question_id: int):
        """Increment question view count"""
        question = self.get_question(question_id)
        if question:
            self.db.query(DBQuestion).filter(DBQuestion.id == question_id).update({DBQuestion.views: DBQuestion.views + 1})
            
            # Log the view increment
            self._log_db_update(
                text=f"Incremented view count for question {question_id}",
                table_name="questions",
                update_type="update",
                values={"question_id": question_id, "view_increment": 1},
                user_id=None  # Views are typically not tied to a specific user
            )
            
            self.db.commit()
    
    def get_site_stats(self) -> Dict[str, int]:
        """Get site statistics"""
        return {
            "total_questions": self.db.query(DBQuestion).count(),
            "total_answers": self.db.query(DBAnswer).count(),
            "total_users": self.db.query(User).count(),
            "total_tags": self.db.query(Tag).count()
        }

    def get_all_users(self) -> List[User]:
        """Get all users from the database"""
        return self.db.query(User).all()

    def update_question(self, question_id: int, question: QuestionCreate):
        db_question = self.get_question(question_id)
        if db_question:
            author_id = cast(int, db_question.author_id)
            self.db.query(DBQuestion).filter(DBQuestion.id == question_id).update({
                DBQuestion.title: question.title,
                DBQuestion.body: question.body,
                DBQuestion.updated_at: datetime.utcnow()
            })
            
            # Log the question update
            self._log_db_update(
                text=f"Updated question {question_id}: title='{question.title}'",
                table_name="questions",
                update_type="update",
                values={"question_id": question_id, "title": question.title, "body_length": len(question.body)},
                user_id=author_id
            )
            
            self.db.commit()
            db_question = self.get_question(question_id)  # Refresh the object
        return db_question

    def delete_question(self, question_id: int) -> bool:
        db_question = self.get_question(question_id)
        if db_question:
            self.db.delete(db_question)
            self.db.commit()
            return True
        return False

    def get_answer(self, answer_id: int):
        return self.db.query(DBAnswer).filter(DBAnswer.id == answer_id).first()

    def update_answer(self, answer_id: int, answer: AnswerCreate):
        db_answer = self.get_answer(answer_id)
        if db_answer:
            self.db.query(DBAnswer).filter(DBAnswer.id == answer_id).update({DBAnswer.body: answer.body})
            self.db.commit()
            db_answer = self.get_answer(answer_id)  # Refresh the object
        return db_answer

    def delete_answer(self, answer_id: int) -> bool:
        db_answer = self.get_answer(answer_id)
        if db_answer:
            self.db.delete(db_answer)
            self.db.commit()
            return True
        return False

    def get_tags(self, page: int = 1, limit: int = 20, search: Optional[str] = None, sort: str = "popular") -> PaginatedResponse:
        """Get paginated list of tags with optional search and sorting"""
        # Print out the parameters for debugging
        print(f"DataService.get_tags called with: page={page}, limit={limit}, search={search}, sort={sort}")
        
        query = self.db.query(Tag)
        
        # Apply search filter if provided
        if search:
            query = query.filter(Tag.name.ilike(f"%{search}%"))
        
        # Apply sorting
        if sort == "popular":
            # Sort by popularity (number of questions using this tag)
            query = query.outerjoin(question_tags).group_by(Tag.id).order_by(func.count(question_tags.c.question_id).desc())
        elif sort == "name":
            # Sort alphabetically by name
            query = query.order_by(Tag.name)
        elif sort == "newest":
            # Sort by creation date, newest first
            query = query.order_by(Tag.created_at.desc())
        
        # Calculate pagination values
        total = query.count()
        total_pages = math.ceil(total / limit)
        skip = (page - 1) * limit
        
        # Get the paginated results
        items = query.offset(skip).limit(limit).all()
        
        result = PaginatedResponse(
            items=items,
            total=total,
            page=page,
            limit=limit
        )
        print(f"DataService.get_tags returning PaginatedResponse with {len(items)} items")
        return result

    def get_tag(self, tag_id: int) -> Optional[Tag]:
        return self.db.query(Tag).filter(Tag.id == tag_id).first()

    def create_tag(self, tag: TagCreate) -> Tag:
        db_tag = Tag(name=tag.name)
        self.db.add(db_tag)
        
        # Log the tag creation
        self._log_db_update(
            text=f"Created new tag '{tag.name}'",
            table_name="tags",
            update_type="insert",
            values={"name": tag.name},
            user_id=None  # Tag creation is typically system-level
        )
        
        self.db.commit()
        self.db.refresh(db_tag)
        return db_tag

    def update_tag(self, tag_id: int, tag: TagCreate):
        db_tag = self.get_tag(tag_id)
        if db_tag:
            self.db.query(Tag).filter(Tag.id == tag_id).update({Tag.name: tag.name})
            self.db.commit()
            db_tag = self.get_tag(tag_id)  # Refresh the object
        return db_tag

    def delete_tag(self, tag_id: int) -> bool:
        db_tag = self.get_tag(tag_id)
        if db_tag:
            self.db.delete(db_tag)
            self.db.commit()
            return True
        return False

    def add_tag_to_question(self, question_id: int, tag_id: int) -> bool:
        question = self.get_question(question_id)
        tag = self.get_tag(tag_id)
        if question and tag:
            stmt = insert(question_tags).values(question_id=question_id, tag_id=tag_id)
            self.db.execute(stmt)
            self.db.commit()
            return True
        return False

    def remove_tag_from_question(self, question_id: int, tag_id: int) -> bool:
        stmt = delete(question_tags).where(
            question_tags.c.question_id == question_id,
            question_tags.c.tag_id == tag_id
        )
        result = self.db.execute(stmt)
        
        if result.rowcount > 0:
            # Log the tag removal
            self._log_db_update(
                text=f"Removed tag {tag_id} from question {question_id}",
                table_name="question_tags",
                update_type="delete",
                values={"question_id": question_id, "tag_id": tag_id},
                user_id=None  # Tag removal might not always have a specific user context
            )
        
        self.db.commit()
        return result.rowcount > 0

    def get_user_vote_on_question(self, question_id: int, user_id: int) -> Optional[str]:
        """Get user's vote on a question"""
        vote = self.db.query(Vote).filter(
            Vote.user_id == user_id,
            Vote.question_id == question_id
        ).first()
        
        if vote:
            return cast(str, vote.vote_type)
        return None
    
    def get_user_vote_on_answer(self, answer_id: int, user_id: int) -> Optional[str]:
        """Get user's vote on an answer"""
        vote = self.db.query(Vote).filter(
            Vote.user_id == user_id,
            Vote.answer_id == answer_id
        ).first()
        
        if vote:
            return cast(str, vote.vote_type)
        return None
    
    def get_user_votes_on_question_answers(self, question_id: int, user_id: int) -> Dict[int, str]:
        """Get user's votes on all answers for a question"""
        # First get all answer IDs for this question
        answer_ids = self.db.query(DBAnswer.id).filter(DBAnswer.question_id == question_id).all()
        answer_ids = [cast(int, aid[0]) for aid in answer_ids]
        
        # Get user votes on these answers
        votes = self.db.query(Vote).filter(
            Vote.user_id == user_id,
            Vote.answer_id.in_(answer_ids)
        ).all()
        
        return {cast(int, vote.answer_id): cast(str, vote.vote_type) for vote in votes}

    # Comment methods
    def create_comment(self, question_id: Optional[int], answer_id: Optional[int], user_id: int, content: str):
        """Create a new comment on a question or answer"""
        from .db.models import Comment as DBComment
        
        # Validate that comment is either on question or an answer, not both
        if (question_id is None and answer_id is None) or (question_id is not None and answer_id is not None):
            raise ValueError("Comment must be on either a question or an answer, not both or neither")
            
        # Verify the target exists
        if question_id:
            question = self.get_question(question_id)
            if not question:
                raise ValueError("Question not found")
        
        if answer_id:
            answer = self.db.query(DBAnswer).filter(DBAnswer.id == answer_id).first()
            if not answer:
                raise ValueError("Answer not found")
        
        # Create comment
        comment = DBComment(
            body=content,
            author_id=user_id,
            question_id=question_id,
            answer_id=answer_id
        )
        
        self.db.add(comment)
        
        # Log the comment creation
        target_type = "question" if question_id else "answer"
        target_id = question_id if question_id else answer_id
        self._log_db_update(
            text=f"User {user_id} created comment on {target_type} {target_id}",
            table_name="comments",
            update_type="insert",
            values={"author_id": user_id, "question_id": question_id, "answer_id": answer_id, "body_length": len(content)},
            user_id=user_id
        )
        
        self.db.commit()
        self.db.refresh(comment)
        
        return comment
    
    def get_comments_for_question(self, question_id: int):
        """Get all comments for a question"""
        from .db.models import Comment as DBComment
        
        return self.db.query(DBComment).filter(
            DBComment.question_id == question_id
        ).order_by(DBComment.created_at.desc()).all()
    
    def get_comments_for_answer(self, answer_id: int):
        """Get all comments for an answer"""
        from .db.models import Comment as DBComment
        
        return self.db.query(DBComment).filter(
            DBComment.answer_id == answer_id
        ).order_by(DBComment.created_at.desc()).all()
    
    def vote_comment(self, comment_id: int, user_id: int):
        """Vote on a comment - only upvotes allowed"""
        from .db.models import Comment as DBComment, CommentVote
        
        comment = self.db.query(DBComment).filter(DBComment.id == comment_id).first()
        if not comment:
            raise ValueError("Comment not found")
            
        # Check if user has already voted on this comment
        existing_vote = self.db.query(CommentVote).filter(
            CommentVote.user_id == user_id,
            CommentVote.comment_id == comment_id
        ).first()
        
        if existing_vote:
            # User is trying to vote again - remove the vote (toggle)
            self.db.delete(existing_vote)
            
            # Log vote removal
            self._log_db_update(
                text=f"User {user_id} removed upvote from comment {comment_id}",
                table_name="comment_votes",
                update_type="delete",
                values={"comment_id": comment_id, "user_id": user_id},
                user_id=user_id
            )
            
            self.db.query(DBComment).filter(DBComment.id == comment_id).update({
                DBComment.votes: DBComment.votes - 1
            })
            
            # Log comment vote count update
            self._log_db_update(
                text=f"Decremented vote count for comment {comment_id} (vote removal)",
                table_name="comments",
                update_type="update",
                values={"comment_id": comment_id, "vote_delta": -1, "reason": "vote_removal"},
                user_id=user_id
            )
        else:
            # Create new vote
            new_vote = CommentVote(
                user_id=user_id,
                comment_id=comment_id
            )
            self.db.add(new_vote)
            
            # Log new vote
            self._log_db_update(
                text=f"User {user_id} upvoted comment {comment_id}",
                table_name="comment_votes",
                update_type="insert",
                values={"comment_id": comment_id, "user_id": user_id},
                user_id=user_id
            )
            
            # Update comment vote count
            self.db.query(DBComment).filter(DBComment.id == comment_id).update({
                DBComment.votes: DBComment.votes + 1
            })
            
            # Log comment vote count update
            self._log_db_update(
                text=f"Incremented vote count for comment {comment_id} (new upvote)",
                table_name="comments",
                update_type="update",
                values={"comment_id": comment_id, "vote_delta": 1, "reason": "new_upvote"},
                user_id=user_id
            )
        
        self.db.commit()
    
    def get_user_comment_vote(self, comment_id: int, user_id: int) -> bool:
        """Check if user has voted on a comment"""
        from .db.models import CommentVote
        
        vote = self.db.query(CommentVote).filter(
            CommentVote.user_id == user_id,
            CommentVote.comment_id == comment_id
        ).first()
        
        return vote is not None
    
    def remove_question_vote(self, question_id: int, user_id: int, vote_type: str):
        """Remove a user's vote from a question"""
        question = self.get_question(question_id)
        if not question:
            raise ValueError("Question not found")
            
        # Find the existing vote
        existing_vote = self.db.query(Vote).filter(
            Vote.user_id == user_id,
            Vote.question_id == question_id,
            Vote.vote_type == vote_type
        ).first()
        
        if not existing_vote:
            # User doesn't have this type of vote on this question, so nothing to remove
            return
            
        # Remove the vote effect from the question
        vote_delta = -1 if vote_type == "up" else 1  # Opposite of the original vote
        self.db.query(DBQuestion).filter(DBQuestion.id == question_id).update({
            DBQuestion.votes: DBQuestion.votes + vote_delta
        })
        
        # Log question vote count update
        self._log_db_update(
            text=f"Updated question {question_id} vote count by {vote_delta} (vote removal)",
            table_name="questions",
            update_type="update",
            values={"question_id": question_id, "vote_delta": vote_delta, "reason": "vote_removal"},
            user_id=user_id
        )
        
        # Delete the vote record
        self.db.delete(existing_vote)
        
        # Log vote removal
        self._log_db_update(
            text=f"User {user_id} removed {vote_type}vote from question {question_id}",
            table_name="votes",
            update_type="delete",
            values={"question_id": question_id, "user_id": user_id, "vote_type": vote_type},
            user_id=user_id
        )
        
        self.db.commit()

    def remove_answer_vote(self, answer_id: int, user_id: int, vote_type: str):
        """Remove a user's vote from an answer"""
        answer = self.get_answer(answer_id)
        if not answer:
            raise ValueError("Answer not found")
            
        # Find the existing vote
        existing_vote = self.db.query(Vote).filter(
            Vote.user_id == user_id,
            Vote.answer_id == answer_id,
            Vote.vote_type == vote_type
        ).first()
        
        if not existing_vote:
            # User doesn't have this type of vote on this answer, so nothing to remove
            return
            
        # Remove the vote effect from the answer
        vote_delta = -1 if vote_type == "up" else 1  # Opposite of the original vote
        self.db.query(DBAnswer).filter(DBAnswer.id == answer_id).update({
            DBAnswer.votes: DBAnswer.votes + vote_delta
        })
        
        # Log answer vote count update
        self._log_db_update(
            text=f"Updated answer {answer_id} vote count by {vote_delta} (vote removal)",
            table_name="answers",
            update_type="update",
            values={"answer_id": answer_id, "vote_delta": vote_delta, "reason": "vote_removal"},
            user_id=user_id
        )
        
        # Delete the vote record
        self.db.delete(existing_vote)
        
        # Log vote removal
        self._log_db_update(
            text=f"User {user_id} removed {vote_type}vote from answer {answer_id}",
            table_name="votes",
            update_type="delete",
            values={"answer_id": answer_id, "user_id": user_id, "vote_type": vote_type},
            user_id=user_id
        )
        
        self.db.commit()
