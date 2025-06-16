#!/usr/bin/env python3
"""
Direct database test to check analytics logs
"""
import requests
import json

def test_direct_question_creation():
    """Test question creation and immediately check for analytics logs"""
    print("=== DIRECT DATABASE TEST ===")
    
    # Create a test question
    question_data = {
        "title": "Direct Test Question",
        "body": "Testing direct analytics logging",
        "author_id": 1,
        "tags": ["test"]
    }
    
    print("Creating question...")
    response = requests.post("http://localhost:8000/questions/", json=question_data)
    
    if response.status_code == 200:
        result = response.json()
        question_id = result["id"]
        print(f"✅ Question created with ID: {question_id}")
        
        # Now vote on it
        print("Voting on question...")
        vote_response = requests.post(f"http://localhost:8000/questions/{question_id}/vote?user_id=2&vote_type=up")
        
        if vote_response.status_code == 200:
            print("✅ Vote successful")
        else:
            print(f"❌ Vote failed: {vote_response.status_code}")
        
        # Check all analytics logs with different session patterns
        session_patterns = [
            "data_service_",
            "anonymous_",
            None  # Get all logs
        ]
        
        for pattern in session_patterns:
            print(f"\nChecking logs with pattern: {pattern}")
            if pattern:
                logs_response = requests.get(f"http://localhost:8000/_synthetic/logs?session_id={pattern}test")
            else:
                # Try to get logs from the synthetic endpoint to see all available
                continue
                
            if logs_response.status_code == 200:
                logs_data = logs_response.json()
                logs = logs_data.get('logs', [])
                print(f"Found {len(logs)} logs")
                
                for log in logs[-3:]:  # Show last 3 logs
                    print(f"  - Event: {log.get('event_type')}, Session: {log.get('session_id')}")
            else:
                print(f"Failed to get logs: {logs_response.status_code}")
        
    else:
        print(f"❌ Question creation failed: {response.status_code}")

def check_all_analytics_logs():
    """Try to check if there are any analytics logs at all"""
    print("\n=== CHECKING ALL ANALYTICS LOGS ===")
    
    # Try some common session ID patterns that might be used by our logging
    import time
    timestamp_pattern = str(int(time.time()))
    
    patterns = [
        "data_service_test",
        f"data_service_{timestamp_pattern}",
        "test_session",
        "debug_test"
    ]
    
    total_logs = 0
    for pattern in patterns:
        response = requests.get(f"http://localhost:8000/_synthetic/logs?session_id={pattern}")
        if response.status_code == 200:
            logs = response.json().get('logs', [])
            total_logs += len(logs)
            if logs:
                print(f"Pattern '{pattern}': {len(logs)} logs")
                for log in logs[-2:]:  # Show last 2
                    event_data = log.get('event_data', {})
                    if isinstance(event_data, str):
                        try:
                            event_data = json.loads(event_data)
                        except:
                            pass
                    print(f"  - {log.get('event_type')}: {event_data}")
    
    print(f"\nTotal logs found across all patterns: {total_logs}")

if __name__ == "__main__":
    test_direct_question_creation()
    check_all_analytics_logs()
