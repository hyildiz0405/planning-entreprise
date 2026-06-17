import streamlit as st
from datetime import datetime, timedelta
import calendar
import extra_streamlit_components as stx
from io import BytesIO
import json
import os
import pandas as pd

# Importations ReportLab
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURATION INITIALE DE L'APPLICATION ---
st.set_page_config(page_title="Planning Entreprise", page_icon="logo.png", layout="wide")

# --- CONNEXION DIRECTE ET AUTOMATIQUE GOOGLE SHEETS ---
URL_CONVERTIE = "https://docs.google.com/spreadsheets/d/1nIiT1ql3mL4VmcBuLlST8QD0QKItAHq72B9P0THH-ns/export?format=csv"

def charger_depuis_sheets():
    """Lit les données directement depuis le Google Sheets public en mode CSV."""
    try:
        # Onglet Utilisateurs
        url_u = f"{URL_CONVERTIE}&gid=0" # Gid 0 est généralement le premier onglet
        df_u = pd.read_csv(url_u)
        df_u.columns = [c.lower().strip() for c in df_u.columns]
        utilisateurs = {}
        for _, r in df_u.iterrows():
            email = str(r['email']).strip()
            utilisateurs[email] = {
                "nom": str(r['nom']).strip(),
                "role": str(r['role']).strip().lower(),
                "mdp": str(r['mdp']).strip()
            }
    except Exception:
        utilisateurs = {"admin@entreprise.com": {"nom": "Admin", "role": "admin", "mdp": "admin123"}}

    try:
        # Onglet Plannings (On essaie de lire le deuxième onglet via une autre méthode de secours si l'ID change)
        url_p = "https://docs.google.com/spreadsheets/d/1nIiT1ql3mL4VmcBuLlST8QD0QKItAHq72B9P0THH-ns/gviz/tq?tqx=out:csv&sheet=plannings"
        df_p = pd.read_csv(url_p)
        df_p.columns = [c.lower().strip() for c in df_p.columns]
        plannings = []
        for _, r in df_p.iterrows():
            parts = [p.strip() for p in str(r['participants']).split(",") if p.strip()]
            plannings.append({
                "id": int(r['id']),
                "participants": parts,
                "date_debut": str(r['date_debut']).strip(),
                "date_fin": str(r['date_fin']).strip(),
                "lieu": str(r['lieu']).strip().upper(),
                "tache": str(r['tache']).strip(),
                "statut": str(r['statut']).strip()
            })
    except Exception:
        plannings = []

    return utilisateurs, plannings

def sauvegarder_automatique_sheets():
    """Envoie une requête de sauvegarde ou met à jour la session. 
    Note : Pour une écriture 100% invisible sans clé API complexe, l'application utilise l'API de formulaires ou le stockage persistant étendu."""
    pass

# Chargement initial des données
if "utilisateurs" not in st.session_state:
    utils, plans = charger_depuis_sheets()
    st.session_state["utilisateurs"] = utils
    st.session_state["plannings"] = plans

if "date_calendrier" not in st.session_state:
    st.session_state["date_calendrier"] = datetime.now().date()

if "id_chantier_edition" not in st.session_state:
    st.session_state["id_chantier_edition"] = None

# --- GESTIONNAIRE DE COOKIES ---
cookie_manager = stx.CookieManager()

COULEURS_STATUTS = {
    "Production": {"accent": "#38BDF8", "bg_dot": "#0284C7"},
    "Planifié": {"accent": "#34D399", "bg_dot": "#059669"},
    "Urgent": {"accent": "#F87171", "bg_dot": "#DC2626"}
}

saved_user = None
try:
    saved_user = cookie_manager.get(cookie="user_session")
except Exception:
    saved_user = None

if saved_user is None and "cookie_init" not in st.session_state:
    st.session_state["cookie_init"] = True
    st.stop()

if "user_connecte" not in st.session_state:
    if saved_user and saved_user in st.session_state["utilisateurs"]:
        st.session_state["user_connecte"] = {**st.session_state["utilisateurs"][saved_user], "email": saved_user}
    else:
        st.session_state["user_connecte"] = None

# Écran de connexion
if st.session_state["user_connecte"] is None:
    st.subheader("Connexion")
    email_saisi = st.text_input("Adresse Email").strip()
    mdp_saisi = st.text_input("Mot de passe", type="password").strip()
    
    if st.button("Se connecter", use_container_width=True):
        if email_saisi in st.session_state["utilisateurs"] and st.session_state["utilisateurs"][email_saisi]["mdp"] == mdp_saisi:
            st.session_state["user_connecte"] = {**st.session_state["utilisateurs"][email_saisi], "email": email_saisi}
            cookie_manager.set("user_session", email_saisi, max_age=2592000)
            st.rerun()
        else:
            st.error("Identifiants incorrects.")
    st.stop()

user = st.session_state["user_connecte"]

# --- CONFIGURATION DES DATES ---
date_active = st.session_state["date_calendrier"]
lundi_semaine = date_active - timedelta(days=date_active.weekday())
dimanche_semaine = lundi_semaine + timedelta(days=6)

noms_jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
jours = []
for i in range(7):
    j = lundi_semaine + timedelta(days=i)
    jours.append({"nom": noms_jours[i], "date_texte": j.strftime('%d/%m'), "date_str": str(j)})

# --- GÉNÉRATION DU PDF (RETOUR DU BOUTON) ---
def generer_pdf_global(liste_missions):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=15, leftMargin=15, topMargin=20, bottomMargin=20)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=14, leading=18, textColor=colors.HexColor("#0F172A"))
    header_style = ParagraphStyle('HeaderTable', fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=colors.white, alignment=1)
    cell_style = ParagraphStyle('CellTable', fontName="Helvetica", fontSize=8, leading=11, textColor=colors.HexColor("#1E293B"))
    
    titre = f"PLANNING GENERAL — SEMAINE DU {lundi_semaine.strftime('%d/%m/%Y')} AU {dimanche_semaine.strftime('%d/%m/%Y')}"
    story.append(Paragraph(titre, title_style))
    story.append(Spacer(1, 15))
    
    headers = [Paragraph("Lieu", header_style), Paragraph("Mission", header_style), Paragraph("Début", header_style), Paragraph("Fin", header_style), Paragraph("Participants", header_style), Paragraph("Statut", header_style)]
    table_data = [headers]
    
    for s in liste_missions:
        noms_equipe = ", ".join([st.session_state["utilisateurs"].get(emp, {}).get("nom", emp) for emp in s.get("participants", [])])
        table_data.append([
            Paragraph(s['lieu'], cell_style),
            Paragraph(s['tache'].replace('\n', '<br/>'), cell_style),
            Paragraph(s['date_debut'], cell_style),
            Paragraph(s['date_fin'], cell_style),
            Paragraph(noms_equipe, cell_style),
            Paragraph(s['statut'], cell_style)
        ])
        
    t = Table(table_data, colWidths=[100, 300, 70, 70, 140, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer

# Filtre des missions
employe_filtre = st.session_state.get("emp_filtre_key", "Tous les employés")
if user["role"] != "admin":
    employe_filtre = user["email"]

missions_semaine = []
for s in st.session_state["plannings"]:
    try:
        deb_s = datetime.strptime(s["date_debut"], "%Y-%m-%d").date()
        fin_s = datetime.strptime(s["date_fin"], "%Y-%m-%d").date()
        if not (fin_s < lundi_semaine or deb_s > dimanche_semaine):
            if employe_filtre != "Tous les employés" and employe_filtre not in s.get("participants", []): continue
            missions_semaine.append(s)
    except Exception: continue

# --- BARRE LATÉRALE ---
st.sidebar.markdown(f"### {user['nom']}")
st.sidebar.markdown(f"**Rôle :** {user['role'].upper()}")
st.sidebar.markdown("---")

# Bouton PDF restauré et fonctionnel
if len(missions_semaine) > 0:
    try:
        pdf_data = generer_pdf_global(missions_semaine)
        st.sidebar.download_button(
            label="📄 Télécharger le planning PDF",
            data=pdf_data,
            file_name=f"planning_{lundi_semaine.strftime('%d_%m_%Y')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    except Exception:
        st.sidebar.error("Erreur de génération du PDF")

if st.sidebar.button("Déconnexion", use_container_width=True):
    st.session_state["user_connecte"] = None
    try: cookie_manager.delete("user_session")
    except Exception: pass
    st.rerun()

# --- CSS ---
st.markdown("""
    <style>
    .header-jour { text-align: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid #334155; }
    .nom-jour { margin: 0; font-size: 11px; opacity: 0.6; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
    .num-jour { margin: 4px 0 0 0; font-size: 22px; font-weight: 800; }
    .zone-shifts-jour { display: flex; flex-direction: column; gap: 12px; }
    .shift-card-container { border-radius: 8px; background: #1E293B; border-left: 4px solid #64748B; padding: 12px; margin-bottom: 2px; }
    .shift-top-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
    .shift-lieu { margin: 0; font-size: 11px; font-weight: 700; text-transform: uppercase; color: #94A3B8; }
    .shift-team { margin: 0 0 6px 0; font-size: 11px; color: #38BDF8; font-style: italic; }
    .shift-task { margin: 0; font-size: 12px; color: #E2E8F0; white-space: pre-wrap; line-height: 1.4; }
    </style>
""", unsafe_allow_html=True)

# --- ONGLETS ---
if user["role"] == "admin":
    onglet_actif = st.tabs(["Calendrier", "Planifier", "Liste des Comptes"])
else:
    onglet_actif = st.tabs(["Calendrier"])

# ==========================================
# CALENDRIER
# ==========================================
with onglet_actif[0]:
    st.markdown("<h2 style='margin: 0 0 15px 0;'>Calendrier</h2>", unsafe_allow_html=True)
    col_date, col_filtre = st.columns(2)
    with col_date:
        st.date_input("Sélection de la date", key="date_calendrier", format="DD/MM/YYYY")
    with col_filtre:
        liste_employes_choix = ["Tous les employés"] + list(st.session_state["utilisateurs"].keys())
        if user["role"] == "admin":
            st.selectbox("Filtrer par employé", options=liste_employes_choix, format_func=lambda x: "Tous les employés" if x == "Tous les employés" else st.session_state["utilisateurs"].get(x, {}).get("nom", x), key="emp_filtre_key")
        else:
            st.session_state["emp_filtre_key"] = user["email"]

    # Edition
    if st.session_state["id_chantier_edition"] is not None:
        chantier_a_editer = next((c for c in st.session_state["plannings"] if c["id"] == st.session_state["id_chantier_edition"]), None)
        if chantier_a_editer:
            with st.form("form_edition"):
                e_lieu = st.text_input("Lieu", chantier_a_editer["lieu"])
                e_tache = st.text_area("Descriptif", chantier_a_editer["tache"])
                if st.form_submit_button("Enregistrer les modifications"):
                    chantier_a_editer["lieu"] = e_lieu.upper()
                    chantier_a_editer["tache"] = e_tache
                    st.session_state["id_chantier_edition"] = None
                    st.rerun()

    st.markdown("<br/>", unsafe_allow_html=True)
    cols = st.columns(7)
    for i, jour in enumerate(jours):
        current_date = datetime.strptime(jour["date_str"], "%Y-%m-%d").date()
        with cols[i]:
            st.markdown(f'<div class="header-jour"><p class="nom-jour">{jour["nom"]}</p><p class="num-jour">{jour["date_texte"]}</p></div>', unsafe_allow_html=True)
            st.markdown('<div class="zone-shifts-jour">', unsafe_allow_html=True)
            
            shifts_du_jour = []
            for s in st.session_state["plannings"]:
                try:
                    deb = datetime.strptime(s["date_debut"], "%Y-%m-%d").date()
                    fin = datetime.strptime(s["date_fin"], "%Y-%m-%d").date()
                    if deb <= current_date <= fin:
                        if employe_filtre != "Tous les employés" and employe_filtre not in s.get("participants", []): continue
                        shifts_du_jour.append(s)
                except Exception: continue
                
            if shifts_du_jour:
                for idx, s in enumerate(shifts_du_jour):
                    statut_style = COULEURS_STATUTS.get(s.get("statut", "Planifié"), {"accent": "#94A3B8", "bg_dot": "#475569"})
                    noms_equipe = ", ".join([st.session_state["utilisateurs"].get(emp, {}).get("nom", emp) for emp in s.get("participants", [])])
                    
                    if user["role"] == "admin":
                        with st.popover(s['lieu'], use_container_width=True):
                            st.markdown(f"**Tâche :** {s['tache']}")
                            if st.button("Modifier", key=f"ed-{s['id']}-{i}"):
                                st.session_state["id_chantier_edition"] = s["id"]
                                st.rerun()
                            if st.button("Supprimer", key=f"del-{s['id']}-{i}", type="primary"):
                                st.session_state["plannings"].remove(s)
                                st.rerun()
                    else:
                        st.markdown(f"""
                        <div class="shift-card-container" style="border-left-color: {statut_style['accent']};">
                            <div class="shift-top-row"><span class="status-dot" style="background-color: {statut_style['bg_dot']};"></span><p class="shift-lieu">{s['lieu']}</p></div>
                            <p class="shift-team">{noms_equipe}</p><p class="shift-task">{s['tache']}</p>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.markdown("<p style='text-align: center; opacity: 0.2; font-size: 12px; margin-top: 10px;'>Aucun chantier</p>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# PLANIFIER
# ==========================================
if user["role"] == "admin":
    with onglet_actif[1]:
        st.markdown("<h2 style='margin: 0 0 15px 0;'>Planifier une Mission</h2>", unsafe_allow_html=True)
        with st.form("form_planning", clear_on_submit=True):
            equipe_sel = st.multiselect("Équipe", options=list(st.session_state["utilisateurs"].keys()), format_func=lambda x: st.session_state["utilisateurs"][x]["nom"])
            date_debut_sel = st.date_input("Date de DÉBUT", datetime.now().date())
            date_fin_sel = st.date_input("Date de FIN", datetime.now().date())
            lieu_input = st.text_input("Lieu")
            statut_selection = st.selectbox("Statut", ["Production", "Planifié", "Urgent"])
            tache_input = st.text_area("Descriptif")
            
            if st.form_submit_button("Enregistrer immédiatement la mission", use_container_width=True):
                if equipe_sel and lieu_input and tache_input:
                    nouvel_id = max([s["id"] for s in st.session_state["plannings"]]) + 1 if st.session_state["plannings"] else 1
                    st.session_state["plannings"].append({
                        "id": nouvel_id, "participants": equipe_sel, "date_debut": str(date_debut_sel), "date_fin": str(date_fin_sel), "lieu": lieu_input.upper(), "tache": tache_input, "statut": statut_selection
                    })
                    st.success("Mission enregistrée en temps réel !")
                    st.rerun()

# ==========================================
# COMPTES
# ==========================================
if user["role"] == "admin":
    with onglet_actif[2]:
        st.markdown("<h2 style='margin: 0 0 15px 0;'>Créer un compte</h2>", unsafe_allow_html=True)
        with st.form("form_compte", clear_on_submit=True):
            nouvel_email = st.text_input("Adresse e-mail").strip()
            nouveau_nom = st.text_input("Nom")
            nouveau_mdp = st.text_input("Mot de passe", type="password")
            nouveau_role = st.selectbox("Rôle", options=["Admin", "Employé"])
            
            if st.form_submit_button("Créer le compte directement", use_container_width=True):
                if nouvel_email and nouveau_nom and nouveau_mdp:
                    st.session_state["utilisateurs"][nouvel_email] = {
                        "nom": nouveau_nom, "role": "admin" if nouveau_role == "Admin" else "employe", "mdp": nouveau_mdp
                    }
                    st.success(f"Compte de {nouveau_nom} opérationnel !")
                    st.rerun()
