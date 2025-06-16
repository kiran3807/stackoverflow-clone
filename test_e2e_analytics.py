#!/usr/bin/env python3
"""
End-to-end analytics test simulating frontend operations
"""

import requests
import json
import time
from typing import Dict, Any, Optional

BASE_URL = "http://localhost:8000"

def make_request(method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Make HTTP request and return JSON response"""
    url = f"{BASE_URL}{endpoint}"
    
    if headers is None:
        headers = {"Content-Type": "application/json"}
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, headers=headers)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data, headers=headers)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        print(f"{method} {endpoint} -> {response.status_code}")
        
        if response.status_code >= 400:
            print(f"Error response: {response.text[:200]}...")
            return {"error": response.text, "status_code": response.status_code}
        
        return response.json() if response.content else {}
    except requests.exceptions.JSONDecodeError:
        return {"error": "Invalid JSON response", "status_code": response.status_code}
    except Exception as e:
        print(f"Request failed: {e}")
        return {"error": str(e)}

def simulate_frontend_user_journey():
    """Simulate a complete user journey as if coming from the frontend"""
    print("🚀 Simulating Frontend User Journey")
    print("=" * 50)
    
    operations_performed = []
    
    # Step 1: User asks a question (like clicking "Ask Question" on frontend)
    print("\n📝 Step 1: User asks a question")
    question_data = {
        "title": "How to implement real-time notifications in React?",
        "body": "I'm building a social media app and need to implement real-time notifications when users get likes, comments, etc. What's the best approach using React and Node.js?",
        "author_id": 1,  # Assume logged-in user ID 1
        "tags": ["react", "nodejs", "notifications", "realtime"]
    }
    
    question_response = make_request("POST", "/questions/", question_data)
    if "error" not in question_response:
        question_id = question_response.get("id")
        print(f"✅ Question created with ID: {question_id}")
        operations_performed.append(f"CREATE_QUESTION_{question_id}")
    else:
        print("❌ Failed to create question")
        return operations_performed
    
    # Step 2: Another user views the question (increment views)
    print("\n👀 Step 2: Users view the question")
    # Simulate multiple users viewing (this would happen when they click on the question)
    for i in range(3):
        view_response = make_request("GET", f"/questions/{question_id}")
        if "error" not in view_response:
            print(f"✅ Question viewed by user (view {i+1})")
        time.sleep(0.5)
    
    # Step 3: Users vote on the question (like clicking upvote/downvote buttons)
    print("\n⬆️ Step 3: Users vote on the question")
    
    # User 2 upvotes
    vote_response_1 = make_request("POST", f"/questions/{question_id}/vote?vote_type=up&user_id=2")
    if "error" not in vote_response_1:
        print("✅ User 2 upvoted the question")
        operations_performed.append(f"UPVOTE_QUESTION_{question_id}_USER_2")
    
    # User 3 upvotes  
    vote_response_2 = make_request("POST", f"/questions/{question_id}/vote?vote_type=up&user_id=3")
    if "error" not in vote_response_2:
        print("✅ User 3 upvoted the question")
        operations_performed.append(f"UPVOTE_QUESTION_{question_id}_USER_3")
    
    # Step 4: Users provide answers (like clicking "Add Answer")
    print("\n💬 Step 4: Users provide answers")
    
    # First answer
    answer_data_1 = {
        "body": "For real-time notifications in React with Node.js, I recommend using Socket.IO. Here's a basic setup:\n\n1. Install socket.io on both client and server\n2. Set up Socket.IO server in your Node.js backend\n3. Connect to the socket in your React components\n4. Emit events when database changes occur\n\nThis approach gives you real-time bidirectional communication perfect for notifications.",
        "question_id": question_id,
        "author_id": 2
    }
    
    # Check what fields the answer endpoint expects
    answer_response_1 = make_request("POST", "/answers/", answer_data_1)
    if "error" not in answer_response_1:
        answer_id_1 = answer_response_1.get("id")
        print(f"✅ First answer created with ID: {answer_id_1}")
        operations_performed.append(f"CREATE_ANSWER_{answer_id_1}_QUESTION_{question_id}")
    else:
        print(f"❌ Failed to create first answer: {answer_response_1.get('error', 'Unknown error')[:100]}")
    
    # Step 5: Users vote on answers
    print("\n⬆️ Step 5: Users vote on answers")
    if 'answer_id_1' in locals() and answer_id_1:
        vote_answer_response = make_request("POST", f"/answers/{answer_id_1}/vote?vote_type=up&user_id=1")
        if "error" not in vote_answer_response:
            print("✅ User 1 upvoted the answer")
            operations_performed.append(f"UPVOTE_ANSWER_{answer_id_1}_USER_1")
    
    print(f"\n🎯 Frontend simulation completed!")
    print(f"Operations performed: {len(operations_performed)}")
    for op in operations_performed:
        print(f"  - {op}")
    
    return operations_performed

def check_analytics_after_frontend_operations(operations_count: int):
    """Check if analytics logs captured the frontend operations"""
    print(f"\n📊 Checking Analytics after Frontend Operations")
    print("=" * 50)
    
    # Get all logs
    logs_response = make_request("GET", "/_synthetic/logs?session_id=all")
    
    if "error" not in logs_response:
        logs = logs_response.get("logs", [])
        db_update_logs = [log for log in logs if log.get("event_type") == "update_db"]
        
        print(f"Total analytics logs: {len(logs)}")
        print(f"DB update logs: {len(db_update_logs)}")
        
        # Show recent logs (last 10)
        recent_logs = db_update_logs[:10]
        print(f"\n📋 Recent DB operations (last 10):")
        for i, log in enumerate(recent_logs, 1):
            event_data = log.get("event_data", {})
            operation = event_data.get("update_type", "unknown").upper()
            table = event_data.get("table_name", "unknown")
            description = event_data.get("text", "No description")
            
            print(f"  {i}. {operation} on {table}: {description}")
        
        # Look for logs related to our operations
        react_question_logs = [
            log for log in db_update_logs 
            if "real-time notifications" in log.get("event_data", {}).get("text", "").lower()
        ]
        
        print(f"\n🔍 Logs related to our React question: {len(react_question_logs)}")
        for log in react_question_logs:
            event_data = log.get("event_data", {})
            print(f"  - {event_data.get('update_type', '').upper()} on {event_data.get('table_name', '')}: {event_data.get('text', '')}")
        
        return len(db_update_logs) > 0
    else:
        print(f"❌ Failed to get analytics logs: {logs_response.get('error', 'Unknown error')}")
        return False

def main():
    """Main end-to-end test function"""
    print("🔥 End-to-End Analytics Test - Frontend Simulation")
    print("=" * 60)
    
    # Simulate frontend user journey
    operations = simulate_frontend_user_journey()
    
    # Wait for logs to be processed
    time.sleep(2)
    
    # Check analytics
    analytics_working = check_analytics_after_frontend_operations(len(operations))
    
    print("\n" + "=" * 60)
    print("📊 END-TO-END TEST RESULTS")
    print("=" * 60)
    
    if analytics_working and len(operations) > 0:
        print("✅ END-TO-END TEST PASSED")
        print("   - Frontend operations executed successfully")
        print("   - Analytics logging captured DB modifications")
        print("   - Full stack analytics integration working!")
    else:
        print("❌ END-TO-END TEST FAILED")
        if len(operations) == 0:
            print("   - No frontend operations completed successfully")
        if not analytics_working:
            print("   - Analytics logging not working properly")
    
    print("\n✨ Test completed!")

if __name__ == "__main__":
    main()
