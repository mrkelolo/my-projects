from pathlib import Path

path = Path("c:/Users/HomePC/Desktop/Pyhton Projects/kelly's dairy/kellys_dairy.py")
text = path.read_text(encoding="utf-8")
start = text.index("    def export_to_txt")
end = text.index("    def _generate_id")
new_block = '''    def export_to_txt(self, filepath: str):
        """Export all notes to a text file."""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"{APP_NAME} - Export\\n")
            f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}\\n")
            f.write("=" * 50 + "\\n")
            for note in self.notes:
                if note.get("archived"):
                    continue
                f.write(f"📌 {note['title']}\\n")
                f.write(f"   Category: {note.get('category', 'General')}\\n")
                f.write(f"   Tags: {', '.join(note.get('tags', []))}\\n")
                f.write(f"   Created: {note['created_at'][:10]}\\n")
                f.write("-" * 40 + "\\n")
                f.write(note['content'] + "\\n")

'''
updated = text[:start] + new_block + text[end:]
path.write_text(updated, encoding="utf-8")
print("Repaired export block")
