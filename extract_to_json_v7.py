import re
import json
import csv
from collections import defaultdict

# Caminho do PDF traduzido
pdf_path = "setembro.pdf"

# Saídas
out_json = "faiths_checkbook_structured.json"
out_csv = "faiths_checkbook_for_translation.csv"

def extract_text_any(path):
    """Extrai texto de um PDF usando pdfplumber, PyPDF2 ou pdfminer.six"""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            pages = []
            for p in pdf.pages:
                pages.append(p.extract_text() or "")
            return "\n\n".join(pages)
    except Exception:
        pass
    try:
        from PyPDF2 import PdfReader
        r = PdfReader(path)
        pages = [p.extract_text() or "" for p in r.pages]
        return "\n\n".join(pages)
    except Exception:
        pass
    from pdfminer.high_level import extract_text as pm_extract_text
    return pm_extract_text(path)

# Lista de livros bíblicos (PT + EN)
BOOKS = [
    "Gênesis","Genesis","Êxodo","Exodus","Levítico","Leviticus","Números","Numbers","Deuteronômio","Deuteronomy",
    "Josué","Joshua","Juízes","Judges","Rute","Ruth","1 Samuel","2 Samuel","1 Reis","2 Reis",
    "1 Crônicas","2 Crônicas","Esdras","Ezra","Neemias","Nehemiah","Ester","Esther","Jó","Job",
    "Salmos","Salmo","Psalms","Psalm","Provérbios","Proverbs","Eclesiastes","Ecclesiastes",
    "Cântico dos Cânticos","Cantares","Song of Solomon","Isaías","Isaiah","Jeremias","Jeremiah",
    "Lamentações","Lamentations","Ezequiel","Ezekiel","Daniel","Oséias","Hosea","Joel","Joel",
    "Amós","Amos","Obadias","Obadiah","Jonas","Jonah","Miquéias","Micah","Naum","Nahum",
    "Habacuque","Habakkuk","Sofonias","Zephaniah","Ageu","Haggai","Zacarias","Zechariah","Malaquias","Malachi",
    "Mateus","Matthew","Marcos","Mark","Lucas","Luke","João","John","Atos","Acts","Romanos","Romans",
    "1 Coríntios","2 Coríntios","1 Corinthians","2 Corinthians","Gálatas","Galatians","Efésios","Ephesians",
    "Filipenses","Philippians","Colossenses","Colossians","1 Tessalonicenses","2 Tessalonicenses",
    "1 Thessalonians","2 Thessalonians","1 Timóteo","2 Timóteo","Tito","Titus","Filemom","Philemon",
    "Hebreus","Hebrews","Tiago","James","1 Pedro","2 Pedro","1 Peter","2 Peter","1 João","2 João","3 João",
    "1 John","2 John","3 John","Judas","Jude","Apocalipse","Revelation"
]

books_escaped = [re.escape(b) for b in BOOKS]
books_alternatives = "|".join(sorted(books_escaped, key=len, reverse=True))
book_ref_re = re.compile(r'(?P<ref>(?:[1-3]\s+)?(?:' + books_alternatives + r')\s+\d{1,3}:\d{1,3}(?:-\d{1,3})?)', re.IGNORECASE)

# Pattern de mês + dia
months_re = r'(JANEIRO|FEVEREIRO|MARCO|MARÇO|ABRIL|MAIO|JUNHO|JULHO|AGOSTO|SETEMBRO|OUTUBRO|NOVEMBRO|DEZEMBRO|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)'
pattern_global = re.compile(r'\b' + months_re + r'\s+(\d{1,2})\b', re.IGNORECASE)

def parse_entries(norm):
    matches = list(pattern_global.finditer(norm))
    entries = defaultdict(list)

    for idx, m in enumerate(matches):
        month = m.group(1).strip().upper()
        day = int(m.group(2))
        start = m.end()
        end = matches[idx+1].start() if idx+1 < len(matches) else len(norm)
        content = norm[start:end].strip()
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]

        # --- título ---
        title = lines[0] if len(lines) > 0 else ""
        title = title.strip('"').strip("'").strip()

        verse_text = ""
        verse_ref = ""
        verse_line_idx = None

        # --- caso 1: versículo e referência na mesma linha ---
        for i in range(1, min(len(lines), 12)):
            rr = book_ref_re.search(lines[i])
            if rr:
                verse_ref = rr.group('ref').strip()
                verse_line_idx = i
                seg = lines[1:i+1]  # do logo após o título até a linha com referência
                seg[-1] = seg[-1].replace(rr.group('ref'), '').strip(' -—:;')
                verse_text = " ".join(seg).strip().strip('"').strip()
                break

        # --- caso 2: linha com aspas + linha seguinte só com referência ---
        if not verse_ref:
            for i in range(1, min(len(lines)-1, 12)):
                q = re.search(r'["“](.+?)["”]', lines[i])
                rr = book_ref_re.search(lines[i+1])
                if q and rr:
                    verse_text = q.group(1).strip()
                    verse_ref = rr.group('ref').strip()
                    verse_line_idx = i+1  # corpo começa depois da linha da referência
                    break

        # --- corpo ---
        if verse_line_idx is not None:
            body_lines = lines[verse_line_idx+1:]
        else:
            body_lines = lines[1:]
        body = "\n\n".join(body_lines).strip()

        entries[month].append({
            "dia": day,
            "titulo": title,
            "versiculo": (verse_text + (" — " + verse_ref if verse_ref else "")).strip(),
            "texto": body
        })

    # ordena os dias dentro de cada mês
    for mes in entries:
        entries[mes] = sorted(entries[mes], key=lambda x: x["dia"])

    return entries

def main():
    raw = extract_text_any(pdf_path)
    if not raw or not raw.strip():
        raise RuntimeError("Não conseguiu extrair texto do PDF.")

    norm = raw.replace('\r','\n')
    norm = norm.replace('“','"').replace('”','"').replace('„','"').replace("’","'").replace("‘","'")
    norm = re.sub(r'\n{3,}', '\n\n', norm).strip()

    entries = parse_entries(norm)

    # Salva JSON (organizado por mês)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    # Também salva CSV (linear, para edição rápida)
    with open(out_csv, "w", encoding="utf-8", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["mes","dia","titulo","versiculo","texto"])
        for mes, dias in entries.items():
            for it in dias:
                writer.writerow([mes, it["dia"], it["titulo"], it["versiculo"], it["texto"]])

    print(f"✅ Concluído. Entradas: {sum(len(v) for v in entries.values())}")
    print("JSON gerado:", out_json)
    print("CSV gerado :", out_csv)

if __name__ == "__main__":
    main()
