#!/usr/bin/env python3
"""
Comprehensive test script to verify AnalyticsLog entries are being created
for all database modification operations in DataService.
"""
import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"

def print_separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def get_analytics_logs():
    """Get recent analytics logs from the synthetic endpoint"""
    try:
        # Using anonymous session for logs
        response = requests.get(f"{BASE_URL}/_synthetic/logs?session_id=anonymous_test")
        if response.status_code == 200:
            return response.json().get('logs', [])
        else:
            print(f"Failed to get logs: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error getting logs: {e}")
        return []

def count_update_db_logs(logs):
    """Count logs with event_type 'update_db'"""
    return len([log for log in logs if log.get('event_type') == 'update_db'])

def test_create_operations():
    """Test CREATE operations and verify analytics logging"""
    print_separator("TESTING CREATE OPERATIONS")
    
    initial_logs = get_analytics_logs()
    initial_count = count_update_db_logs(initial_logs)
    print(f"Initial update_db logs count: {initial_count}")
    
    # Test 1: Create User
    print("\n1. Testing create_user...")
    user_data = {
        "username": f"test_user_{int(time.time())}",
        "email": f"test_{int(time.time())}@example.com",
        "password": "TestPassword123!"
    }
    response = requests.post(f"{BASE_URL}/auth/register", json=user_data)
    if response.status_code == 200:
        user_result = response.json()
        print(f"✅ User created successfully: {user_result}")
    else:
        print(f"❌ User creation failed: {response.status_code} - {response.text}")
    
    # Test 2: Create Question
    print("\n2. Testing create_question...")
    question_data = {
        "title": f"Test Question {int(time.time())}",
        "body": "This is a test question for analytics logging",
        "author_id": 1,
        "tags": ["testing", "analytics"]
    }
    response = requests.post(f"{BASE_URL}/questions/", json=question_data)
    if response.status_code == 200:
        question_result = response.json()
        question_id = question_result["id"]
        print(f"✅ Question created successfully: ID {question_id}")
    else:
        print(f"❌ Question creation failed: {response.status_code} - {response.text}")
        question_id = 1  # Fallback
    
    # Test 3: Create Answer
    print("\n3. Testing create_answer...")
    answer_data = {
        "body": "This is a test answer for analytics logging",
        "question_id": question_id,
        "author_id": 2
    }
    response = requests.post(f"{BASE_URL}/answers/", json=answer_data)
    if response.status_code == 200:
        answer_result = response.json()
        answer_id = answer_result["id"]
        print(f"✅ Answer created successfully: ID {answer_id}")
    else:
        print(f"❌ Answer creation failed: {response.status_code} - {response.text}")
        answer_id = 1  # Fallback
    
    # Test 4: Create Comment
    print("\n4. Testing create_comment...")
    comment_data = {
        "body": "This is a test comment for analytics logging",
        "author_id": 1
    }
    response = requests.post(f"{BASE_URL}/comments/question/{question_id}", json=comment_data)
    if response.status_code == 200:
        comment_result = response.json()
        print(f"✅ Comment created successfully: {comment_result}")
    else:
        print(f"❌ Comment creation failed: {response.status_code} - {response.text}")
    
    # Check analytics logs after creates
    time.sleep(1)  # Give some time for logs to be written
    final_logs = get_analytics_logs()
    final_count = count_update_db_logs(final_logs)
    new_logs = final_count - initial_count
    
    print(f"\n📊 Analytics Summary for CREATE operations:")
    print(f"   New update_db logs created: {new_logs}")
    print(f"   Expected: 4-6+ (user, question, tags, answer, comment)")
    
    if new_logs >= 4:
        print("✅ CREATE operations are generating analytics logs!")
    else:
        print("❌ CREATE operations may not be generating enough analytics logs")
    
    return question_id, answer_id

def test_vote_operations(question_id, answer_id):
    """Test VOTE operations and verify analytics logging"""
    print_separator("TESTING VOTE OPERATIONS")
    
    initial_logs = get_analytics_logs()
    initial_count = count_update_db_logs(initial_logs)
    print(f"Initial update_db logs count: {initial_count}")
    
    # Test question voting
    print("\n1. Testing vote_question...")
    response = requests.post(f"{BASE_URL}/questions/{question_id}/vote?user_id=1&vote_type=up")
    if response.status_code == 200:
        print("✅ Question upvote successful")
    else:
        print(f"❌ Question upvote failed: {response.status_code}")
    
    # Test answer voting
    print("\n2. Testing vote_answer...")
    response = requests.post(f"{BASE_URL}/answers/{answer_id}/vote?user_id=1&vote_type=up")
    if response.status_code == 200:
        print("✅ Answer upvote successful")
    else:
        print(f"❌ Answer upvote failed: {response.status_code}")
    
    # Test vote removal
    print("\n3. Testing remove vote...")
    response = requests.post(f"{BASE_URL}/questions/{question_id}/vote?user_id=1&vote_type=up&undo=true")
    if response.status_code == 200:
        print("✅ Question vote removal successful")
    else:
        print(f"❌ Question vote removal failed: {response.status_code}")
    
    # Check analytics logs
    time.sleep(1)
    final_logs = get_analytics_logs()
    final_count = count_update_db_logs(final_logs)
    new_logs = final_count - initial_count
    
    print(f"\n📊 Analytics Summary for VOTE operations:")
    print(f"   New update_db logs created: {new_logs}")
    print(f"   Expected: 6+ (votes + vote count updates + removals)")
    
    if new_logs >= 4:
        print("✅ VOTE operations are generating analytics logs!")
    else:
        print("❌ VOTE operations may not be generating enough analytics logs")

def test_update_operations(question_id):
    """Test UPDATE operations and verify analytics logging"""
    print_separator("TESTING UPDATE OPERATIONS")
    
    initial_logs = get_analytics_logs()
    initial_count = count_update_db_logs(initial_logs)
    print(f"Initial update_db logs count: {initial_count}")
    
    # Test increment views
    print("\n1. Testing increment_question_views...")
    # This is typically called internally, so let's view the question to trigger it
    response = requests.get(f"{BASE_URL}/questions/{question_id}")
    if response.status_code == 200:
        print("✅ Question viewed (should increment views)")
    else:
        print(f"❌ Question view failed: {response.status_code}")
    
    # Test question update
    print("\n2. Testing update_question...")
    update_data = {
        "title": f"Updated Test Question {int(time.time())}",
        "body": "This is an updated test question for analytics logging",
        "author_id": 1,
        "tags": ["testing", "analytics", "updated"]
    }
    response = requests.put(f"{BASE_URL}/questions/{question_id}", json=update_data)
    if response.status_code == 200:
        print("✅ Question updated successfully")
    else:
        print(f"❌ Question update failed: {response.status_code} - {response.text}")
    
    # Check analytics logs
    time.sleep(1)
    final_logs = get_analytics_logs()
    final_count = count_update_db_logs(final_logs)
    new_logs = final_count - initial_count
    
    print(f"\n📊 Analytics Summary for UPDATE operations:")
    print(f"   New update_db logs created: {new_logs}")
    print(f"   Expected: 1-2+ (view increment, question update)")
    
    if new_logs >= 1:
        print("✅ UPDATE operations are generating analytics logs!")
    else:
        print("❌ UPDATE operations may not be generating analytics logs")

def inspect_recent_logs():
    """Inspect the most recent analytics logs to see their structure"""
    print_separator("INSPECTING RECENT ANALYTICS LOGS")
    
    logs = get_analytics_logs()
    update_db_logs = [log for log in logs if log.get('event_type') == 'update_db']
    
    print(f"Total analytics logs: {len(logs)}")
    print(f"Update_db logs: {len(update_db_logs)}")
    
    if update_db_logs:
        print(f"\n🔍 Recent update_db logs (last 5):")
        for i, log in enumerate(update_db_logs[:5]):
            print(f"\n--- Log {i+1} ---")
            print(f"Timestamp: {log.get('timestamp')}")
            print(f"Event Type: {log.get('event_type')}")
            print(f"Session ID: {log.get('session_id')}")
            
            event_data = log.get('event_data')
            if isinstance(event_data, str):
                try:
                    event_data = json.loads(event_data)
                except:
                    pass
            
            if isinstance(event_data, dict):
                print(f"Text: {event_data.get('text', 'N/A')}")
                print(f"Table: {event_data.get('table_name', 'N/A')}")
                print(f"Operation: {event_data.get('update_type', 'N/A')}")
                print(f"Values: {event_data.get('values', {})}")
            else:
                print(f"Event Data: {event_data}")
    else:
        print("❌ No update_db logs found!")

def main():
    """Run comprehensive analytics logging tests"""
    print_separator("ANALYTICS LOGGING TEST SUITE")
    print(f"Started at: {datetime.now()}")
    print(f"Testing against: {BASE_URL}")
    
    try:
        # Test create operations
        question_id, answer_id = test_create_operations()
        
        # Test vote operations
        test_vote_operations(question_id, answer_id)
        
        # Test update operations
        test_update_operations(question_id)
        
        # Inspect logs
        inspect_recent_logs()
        
        print_separator("TEST COMPLETE")
        print("✅ Analytics logging test suite completed!")
        
    except Exception as e:
        print(f"❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
