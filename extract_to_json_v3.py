# extract_to_json_v3.py
import re
import json
import csv

# caminho do PDF traduzido
pdf_path = "janeiro.pdf"

out_json = "faiths_checkbook_structured_v3.json"
out_csv = "faiths_checkbook_for_translation_v3.csv"

def extract_text_any(path):
    """Tenta pdfplumber, PyPDF2, pdfminer"""
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

# Lista de nomes de livros (PT + EN) - você pode estender se quiser
BOOKS = [
    # Portuguese / English pairs and other common forms
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
    "1 Tessalonians","2 Tessalonians","1 Timóteo","2 Timóteo","Tito","Titus","Filemom","Philemon",
    "Hebreus","Hebrews","Tiago","James","1 Pedro","2 Pedro","1 Peter","2 Peter","1 João","2 João","3 João",
    "1 John","2 John","3 John","Judas","Jude","Apocalipse","Revelation"
]

# criar uma alternativa regex escapada a partir da lista
books_escaped = [re.escape(b) for b in BOOKS]
books_alternatives = "|".join(sorted(books_escaped, key=len, reverse=True))  # mais longos primeiro
# pattern: opcional "1 " ou "2 " ou "3 " + nome do livro + espaço + capit:vers
book_ref_re = re.compile(r'(?P<ref>(?:[1-3]\s+)?(?:' + books_alternatives + r')\s+\d{1,3}:\d{1,3}(?:-\d{1,3})?)', re.IGNORECASE)

# pattern para detectar cabeçalho "MÊS <n>"
months_re = r'(JANEIRO|FEVEREIRO|MARCO|MARÇO|ABRIL|MAIO|JUNHO|JULHO|AGOSTO|SETEMBRO|OUTUBRO|NOVEMBRO|DEZEMBRO|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)'
pattern_global = re.compile(r'\b' + months_re + r'\s+(\d{1,2})\b', re.IGNORECASE)

def parse_entries(norm):
    matches = list(pattern_global.finditer(norm))
    entries = []
    for idx, m in enumerate(matches):
        month = m.group(1).strip()
        day = int(m.group(2))
        start = m.end()
        end = matches[idx+1].start() if idx+1 < len(matches) else len(norm)
        content = norm[start:end].strip()
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        title = lines[0] if len(lines) > 0 else ""
        verse_text = ""
        verse_ref = ""
        verse_line_idx = None

        # 1) procurar referência entre as primeiras N linhas (normalmente aparece logo após o título)
        max_search_lines = min(len(lines), 10)
        for i in range(max_search_lines):
            line = lines[i]
            rr = book_ref_re.search(line)
            if rr:
                verse_ref = rr.group('ref').strip()
                verse_line_idx = i
                # pegar até 3 linhas anteriores (ajuste se precisar)
                start_line = max(0, i-3)
                seg = lines[start_line:i+1]
                # remover a referência da última linha
                seg[-1] = seg[-1].replace(rr.group('ref'), '').strip(' -—:;')
                verse_text = " ".join(seg).strip().strip('"').strip()
                break

        # 2) se não encontrou, procurar trecho entre aspas nas primeiras linhas
        if not verse_ref:
            for i in range(min(len(lines), 8)):
                q = re.search(r'["\'](.+?)["\']', lines[i])
                if q:
                    verse_text = q.group(1).strip()
                    # tentar achar referência após as aspas na mesma linha
                    after = lines[i][q.end():].strip()
                    rr = book_ref_re.search(after)
                    if rr:
                        verse_ref = rr.group('ref').strip()
                        verse_line_idx = i
                    break

        # 3) fallback: buscar referência em todo o bloco
        if not verse_ref:
            rr = book_ref_re.search(content)
            if rr:
                verse_ref = rr.group('ref').strip()
                # localizar linha que contém a referência
                ref_line_idx = None
                for i, line in enumerate(lines):
                    if rr.group('ref') in line:
                        ref_line_idx = i
                        break
                if ref_line_idx is None:
                    ref_line_idx = 0
                verse_line_idx = ref_line_idx
                start_line = max(0, ref_line_idx-4)
                seg = lines[start_line:ref_line_idx+1]
                seg[-1] = seg[-1].replace(rr.group('ref'), '').strip(' -—:;')
                verse_text = " ".join(seg).strip().strip('"').strip()

        # corpo do texto
        if verse_line_idx is not None:
            body_lines = lines[verse_line_idx+1:]
        else:
            body_lines = lines[1:]
        body = "\n\n".join(body_lines).strip()

        entries.append({
            "mes": month.upper(),
            "dia": day,
            "titulo": title,
            "versiculo": (verse_text + (" — " + verse_ref if verse_ref else "")).strip(),
            "texto": body
        })
    return entries

def main():
    raw = extract_text_any(pdf_path)
    if not raw or not raw.strip():
        raise RuntimeError("Não conseguiu extrair texto do PDF.")
    norm = raw.replace('\r','\n')
    norm = norm.replace('“','"').replace('”','"').replace('„','"').replace("’","'").replace("‘","'")
    norm = re.sub(r'\n{3,}', '\n\n', norm).strip()
    entries = parse_entries(norm)

    # salva json e csv
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    with open(out_csv, "w", encoding="utf-8", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["mes","dia","titulo","versiculo","texto"])
        for it in entries:
            writer.writerow([it["mes"], it["dia"], it["titulo"], it["versiculo"], it["texto"]])

    print(f"✅ Concluído. Entradas: {len(entries)}")
    print("JSON gerado:", out_json)
    print("CSV gerado :", out_csv)

if __name__ == "__main__":
    main()
