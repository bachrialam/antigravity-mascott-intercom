import markdown

text = """
How to save a JPG file
Follow these steps to export your design as a JPG from the editor:
Step 1: Click the Download button in the top-right corner of the editor.

Why this matters
JPG is a lossy format, so compression can reduce image quality.

[Watch the video](https://cdnp.kittl.com/6c74d212-a931-444e-8fcd-34a5da750087_Create+Download.mp4)
Let me know if you need help!
"""

print(markdown.markdown(text, extensions=['fenced_code', 'tables']))
