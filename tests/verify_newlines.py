
import csv
import os
from db import add_reply, get_pending_replies, REPLIES_CSV

def test_newline_handling():
    test_id = "test_newline_post"
    test_content = "Line 1\nLine 2\nLine 3"
    
    print(f"Adding test reply with content:\n{test_content}")
    add_reply(test_id, "test_handle", test_content, status="test_pending")
    
    replies = get_pending_replies(status="test_pending")
    found = False
    for r in replies:
        if r['target_post_id'] == test_id:
            found = True
            print(f"Retrieved content:\n{r['content']}")
            assert r['content'] == test_content, "Content mismatch!"
            print("✅ Verification Successful: Newlines preserved and CSV remains valid.")
            break
    
    if not found:
        print("❌ Verification Failed: Test reply not found.")

if __name__ == "__main__":
    try:
        test_newline_handling()
    finally:
        # Cleanup: we'll leave it in the CSV for the user to see or you can comment out cleanup
        pass
