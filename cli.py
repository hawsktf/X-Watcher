from db import get_all

def show_cli():
    rows = get_all()

    print("\nTracked handles\n")

    for row in rows:
        handle, _, content, post_time, checked = row

        print("Handle:", handle)
        print("Latest:", content[:120])
        print("Time:", post_time)
        print("Checked:", checked)
        print()

