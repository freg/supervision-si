#!/bin/sh
# Exemple d'action « script » de si-mailbox : reçoit le message en JSON sur l'entrée standard et note la ligne
# (date, expéditeur, sujet, catégorie IA) dans ~/si-mailbox-traces.csv. Copier, adapter, rendre exécutable.
python3 -c 'import json,sys,csv,os,time
m=json.load(sys.stdin)
w=csv.writer(open(os.path.expanduser("~/si-mailbox-traces.csv"),"a",newline=""))
w.writerow([time.strftime("%Y-%m-%d %H:%M",time.localtime(m.get("date") or 0)),m.get("de"),m.get("sujet"),(m.get("ia") or "")[:80],";".join(p["nom"] for p in m.get("pieces") or [])])'
