#!/usr/bin/env python3
"""
Comprehensive test script for analytics logging
Tests both backend DB operations and end-to-end frontend operations
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
            print(f"Error response: {response.text}")
        
        return response.json() if response.content else {}
    except Exception as e:
        print(f"Request failed: {e}")
        return {}

def get_analytics_logs() -> Dict[str, Any]:
    """Get all analytics logs"""
    return make_request("GET", "/_synthetic/logs?session_id=all")

def clear_logs():
    """Clear existing logs by making a test log and checking the response"""
    print("\n=== Checking initial logs ===")
    logs = get_analytics_logs()
    print(f"Initial logs count: {len(logs.get('logs', []))}")
    return logs

def test_backend_operations():
    """Test backend DB operations that should trigger analytics logging"""
    print("\n=== Testing Backend DB Operations ===")
    
    # Test 1: Create User (INSERT)
    print("\n1. Creating user...")
    user_data = {
        "name": "Analytics Test User",
        "email": "analytics@test.com",
        "password": "testpass123",
        "location": "Test City"
    }
    user_response = make_request("POST", "/api/users/", user_data)
    user_id = user_response.get("id")
    print(f"Created user ID: {user_id}")
    
    # Test 2: Create Question (INSERT)
    print("\n2. Creating question...")
    question_data = {
        "title": "Analytics Test Question",
        "body": "This is a test question for analytics logging",
        "tags": ["analytics", "testing"],
        "author_id": user_id or 1
    }
    question_response = make_request("POST", "/questions/", question_data)
    question_id = question_response.get("id")
    print(f"Created question ID: {question_id}")
    
    # Test 3: Create Answer (INSERT)
    if question_id:
        print("\n3. Creating answer...")
        answer_data = {
            "body": "This is a test answer for analytics logging",
            "question_id": question_id,
            "author_id": user_id or 1
        }
        answer_response = make_request("POST", "/answers/", answer_data)
        answer_id = answer_response.get("id")
        print(f"Created answer ID: {answer_id}")
    
    # Test 4: Vote on Question (UPDATE)
    if question_id:
        print("\n4. Voting on question...")
        vote_response = make_request("POST", f"/questions/{question_id}/vote?vote_type=up&user_id={user_id or 1}")
        print(f"Vote response: {vote_response}")
    
    # Test 5: Increment Question Views (UPDATE)
    if question_id:
        print("\n5. Incrementing question views...")
        view_response = make_request("PUT", f"/questions/{question_id}/view")
        print(f"View increment response: {view_response}")
    
    print("\n=== Backend operations completed ===")

def test_frontend_simulation():
    """Simulate frontend operations that trigger backend DB changes"""
    print("\n=== Testing Frontend-like Operations ===")
    
    # Simulate typical frontend flows
    
    # 1. User registration flow
    print("\n1. User registration flow...")
    reg_data = {
        "name": "Frontend Test User",
        "email": "frontend@test.com", 
        "password": "frontendpass123",
        "location": "Frontend City"
    }
    reg_response = make_request("POST", "/api/users/", reg_data)
    frontend_user_id = reg_response.get("id")
    
    # 2. Ask question flow
    print("\n2. Ask question flow...")
    if frontend_user_id:
        ask_data = {
            "title": "How to test analytics in full-stack app?",
            "body": "I need to test analytics logging from frontend to backend...",
            "tags": ["frontend", "backend", "analytics"],
            "author_id": frontend_user_id
        }
        ask_response = make_request("POST", "/questions/", ask_data)
        frontend_question_id = ask_response.get("id")
        
        # 3. Answer the question
        print("\n3. Answer flow...")
        if frontend_question_id:
            ans_data = {
                "body": "You should create comprehensive tests that cover both backend API calls and frontend interactions...",
                "question_id": frontend_question_id,
                "author_id": frontend_user_id
            }
            ans_response = make_request("POST", "/answers/", ans_data)
            
            # 4. Vote on both question and answer
            print("\n4. Voting flow...")
            # Vote on question
            make_request("POST", f"/questions/{frontend_question_id}/vote?vote_type=up&user_id={frontend_user_id}")
            
            # Vote on answer
            answer_id = ans_response.get("id")
            if answer_id:
                make_request("POST", f"/answers/{answer_id}/vote?vote_type=up&user_id={frontend_user_id}")
    
    print("\n=== Frontend simulation completed ===")

def analyze_logs():
    """Analyze the collected analytics logs"""
    print("\n=== Analyzing Analytics Logs ===")
    
    logs = get_analytics_logs()
    log_entries = logs.get("logs", [])
    
    print(f"Total log entries found: {len(log_entries)}")
    
    if not log_entries:
        print("❌ No analytics logs found! This indicates the logging is not working.")
        return False
    
    # Analyze log types
    db_update_logs = [log for log in log_entries if log.get("event_type") == "update_db"]
    other_logs = [log for log in log_entries if log.get("event_type") != "update_db"]
    
    print(f"DB update logs: {len(db_update_logs)}")
    print(f"Other logs: {len(other_logs)}")
    
    # Analyze DB operations
    if db_update_logs:
        print("\n--- DB Update Log Details ---")
        operation_counts = {}
        table_counts = {}
        
        for log in db_update_logs:
            event_data = log.get("event_data", {})
            update_type = event_data.get("update_type", "unknown")
            table_name = event_data.get("table_name", "unknown")
            
            operation_counts[update_type] = operation_counts.get(update_type, 0) + 1
            table_counts[table_name] = table_counts.get(table_name, 0) + 1
            
            print(f"  - {update_type.upper()} on {table_name}: {event_data.get('text', 'No description')}")
        
        print(f"\nOperation summary:")
        for op, count in operation_counts.items():
            print(f"  {op}: {count}")
        
        print(f"\nTable summary:")
        for table, count in table_counts.items():
            print(f"  {table}: {count}")
    
    return len(db_update_logs) > 0

def main():
    """Main test function"""
    print("🔍 Starting Comprehensive Analytics Logging Test")
    print("=" * 60)
    
    # Initial state
    clear_logs()
    
    # Wait a moment for any pending operations to complete
    time.sleep(2)
    
    # Test backend operations
    test_backend_operations()
    
    # Wait for logs to be written
    time.sleep(3)
    
    # Check logs after backend operations
    print("\n=== Checking logs after backend operations ===")
    backend_logs = get_analytics_logs()
    backend_count = len(backend_logs.get("logs", []))
    print(f"Logs after backend operations: {backend_count}")
    
    # Test frontend-like operations
    test_frontend_simulation()
    
    # Wait for logs to be written
    time.sleep(3)
    
    # Final analysis
    success = analyze_logs()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ Analytics logging test PASSED - DB operations are being logged")
    else:
        print("❌ Analytics logging test FAILED - No DB update logs found")
    
    print("Test completed.")

if __name__ == "__main__":
    main()
