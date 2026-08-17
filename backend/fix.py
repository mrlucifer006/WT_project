import re

filepath = r"f:\Personal Projects\Billing\app\main.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Find templates.TemplateResponse( "filename.html", {
# Replace with templates.TemplateResponse(request, "filename.html", {
content = re.sub(
    r'templates\.TemplateResponse\(\s*("[^"]+")\s*,\s*\{',
    r'templates.TemplateResponse(request, \1, {',
    content
)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Replaced successfully")
