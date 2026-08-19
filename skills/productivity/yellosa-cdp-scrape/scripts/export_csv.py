#!/usr/bin/env python3
# Export Yellosa scraped JSON -> CSV.
# Decodes website redirect URLs, strips address noise, flattens Q&A.
# Usage: python3 scripts/export_csv.py <input.json> <output.csv>
import json, csv, sys, urllib.parse, re

def decode_website(w):
    if not w:
        return ''
    m = re.search(r'u=([^&]+)', w)
    return urllib.parse.unquote(m.group(1)) if m else w

def qa_text(b):
    parts = []
    for q in b.get('qa', []):
        qn = (q.get('question') or '').strip()
        an = (q.get('answer') or '').strip()
        if qn:
            parts.append(f"Q: {qn}" + (f" | A: {an}" if an else ""))
    return " || ".join(parts)

cols = ['Name','Email','Address','Contact Number','Mobile Phone','WhatsApp','Website',
        'Establishment Year','Employees','Registration Code','Company Description',
        'Categories','Reviews','Verified','Premium','Q&A','URL']
rows = []
for b in json.load(open(sys.argv[1])):
    rows.append([
        b.get('name',''),
        b.get('email','') if re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', (b.get('email','') or '').strip()) else '',
        (b.get('address') or '').replace('View MapGet Directions','').strip(),
        b.get('contact_number',''),
        b.get('mobile_phone',''),
        b.get('whatsapp',''),
        decode_website(b.get('website','')),
        b.get('establishment_year',''),
        b.get('employees',''),
        b.get('registration_code',''),
        (b.get('company_description') or '').replace('\n',' ').strip(),
        ', '.join(b.get('categories',[])),
        b.get('reviews',''),
        'Yes' if b.get('verified') else 'No',
        'Yes' if b.get('premium') else 'No',
        qa_text(b),
        b.get('url',''),
    ])
with open(sys.argv[2],'w',newline='',encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(cols); w.writerows(rows)
print(f"Wrote {len(rows)} rows -> {sys.argv[2]}")
