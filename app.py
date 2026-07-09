import streamlit as st
from datetime import datetime, timedelta
import calendar
import extra_streamlit_components as stx
import json
import time
import os
import pandas as pd
from io import BytesIO
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import gspread
from google.oauth2.service_account import Credentials

# Importations pour la génération des PDF
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURATION INITIALE DE L'APPLICATION ---
st.set_page_config(page_title="Planning Entreprise", page_icon="logo.png", layout="wide")

# --- CONNEXION À GOOGLE SHEETS VIA SECRETS ---
NOM_DU_SHEET = "Planning Arhen Data"  

@st.cache_resource
def initialiser_gspread():
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets", 
            "https://www.googleapis.com/auth/drive"
        ]
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open(NOM_DU_SHEET)
    except Exception as e:
        st.error(f"Erreur de connexion à Google Sheets : {e}")
        return None

sh = initialiser_gspread()

# --- FONCTION SECURE D'ENVOI DE NOTIFICATION PAR EMAIL ---
def envoyer_notification_email(destinataire, sujet, contenu_html):
    try:
        cfg = st.secrets["email"]
        msg = MIMEMultipart("alternative")
        msg["Subject"] = sujet
        msg["From"] = cfg["expediteur"]
        msg["To"] = destinataire
        
        part = MIMEText(contenu_html, "html")
        msg.attach(part)
        
        with smtplib.SMTP_SSL(cfg["smtp_server"], int(cfg["smtp_port"])) as server:
            server.login(cfg["expediteur"], cfg["mot_de_passe"])
            server.sendmail(cfg["expediteur"], destinataire, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Erreur d'envoi de l'e-mail à {destinataire} : {e}")
        return False

# --- FONCTION POUR GÉNÉRER LE PDF DU PLANNING SEMAINE ---
def generer_pdf_planning(jours, plannings, utilisateurs, employe_filtre):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    
    titre_texte = f"PLANNING DE LA SEMAINE — Du {jours[0]['date_texte']} au {jours[-1]['date_texte']}"
    if employe_filtre != "Tous les utilisateurs" and employe_filtre in utilisateurs:
        titre_texte += f" — {utilisateurs[employe_filtre]['nom']}"
        
    style_titre = ParagraphStyle('Titre', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor("#0284C7"), spaceAfter=15, alignment=1)
    story.append(Paragraph(titre_texte, style_titre))
    story.append(Spacer(1, 10))
    
    headers = [f"{j['nom']}\n({j['date_texte']})" for j in jours]
    donnees_tableau = [headers]
    
    filtre_cle = employe_filtre.strip().lower() if employe_filtre != "Tous les utilisateurs" else "Tous les utilisateurs"

    ligne_chantiers = []
    for jour in jours:
        current_date = datetime.strptime(jour["date_str"], "%Y-%m-%d").date()
        textes_du_jour = []
        
        for s in plannings:
            if not s.get("date_debut"): continue
            try:
                d_deb = datetime.strptime(str(s["date_debut"]), "%Y-%m-%d").date()
                d_fin = datetime.strptime(str(s["date_fin"]), "%Y-%m-%d").date()
                if d_deb <= current_date <= d_fin:
                    participants_clean = [str(p).strip().lower() for p in s.get("participants", [])]
                    
                    if filtre_cle == "Tous les utilisateurs" or filtre_cle in participants_clean:
                        noms_equipe = ", ".join([utilisateurs[emp]["nom"] for emp in s.get("participants", []) if emp in utilisateurs])
                        info_mission = f"<b>{s['lieu']}</b><br/><i>Eq: {noms_equipe}</i><br/>{s['tache']}"
                        textes_du_jour.append(info_mission)
            except:
                continue
                
        if textes_du_jour:
            cell_content = "<br/><br/>-------------------<br/><br/>".join(textes_du_jour)
        else:
            cell_content = "<font color='gray'>Aucun chantier</font>"
            
        style_cellule = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=9, leading=12)
        ligne_chantiers.append(Paragraph(cell_content, style_cellule))
        
    donnees_tableau.append(ligne_chantiers)
    
    largeur_colonne = 100
    t = Table(donnees_tableau, colWidths=[largeur_colonne]*7)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0284C7")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#FAFAFA")),
    ]))
    
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- FONCTION POUR GÉNÉRER LE PDF D'UN RAPPORT ---
def generer_pdf_rapport(rapport):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()
    
    style_titre = ParagraphStyle('Titre', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor("#0284C7"), spaceAfter=15)
    style_label = ParagraphStyle('Label', parent=styles['Normal'], fontSize=11, fontName="Helvetica-Bold", spaceAfter=5)
    style_texte = ParagraphStyle('Texte', parent=styles['Normal'], fontSize=11, leading=14, spaceAfter=15)
    
    story.append(Paragraph(f"RAPPORT D'ACTIVITÉ - {rapport.get('projet', '')}", style_titre))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Utilisateur :", style_label))
    story.append(Paragraph(rapport.get('employe', 'Inconnu'), style_texte))
    story.append(Paragraph("Date de soumission :", style_label))
    story.append(Paragraph(rapport.get('date', ''), style_texte))
    story.append(Paragraph("Détails du travail accompli :", style_label))
    story.append(Paragraph(rapport.get('contenu', '').replace('\n', '<br/>'), style_texte))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- FONCTIONS DE SAUVEGARDE ET CHARGEMENT VIA GOOGLE SHEETS ---
def charger_utilisateurs_sheets():
    if not sh: return UTILISATEURS_PAR_DEFAUT
    try:
        ws = sh.worksheet("utilisateurs")
        records = ws.get_all_records()
        if not records: return UTILISATEURS_PAR_DEFAUT
        users_dict = {}
        for r in records:
            users_dict[str(r["identifiant"]).strip().lower()] = {
                "nom": r["nom"], "role": str(r["role"]).strip().lower(), "mdp": str(r["mdp"]), "tel": str(r["tel"]), "email_contact": r["email_contact"]
            }
        return users_dict
    except Exception: return UTILISATEURS_PAR_DEFAUT

def sauvegarder_utilisateur_sheets(identifiant, infos):
    if not sh: return
    try:
        ws = sh.worksheet("utilisateurs")
        # Alignement strict des 6 colonnes (A à F) pour éviter le décalage
        ligne = [
            str(identifiant).strip().lower(),
            str(infos.get("nom", "")),
            str(infos.get("role", "employe")),
            str(infos.get("mdp", "")),
            str(infos.get("tel", "")),
            str(infos.get("email_contact", ""))
        ]
        ws.append_row(ligne, value_input_option='USER_ENTERED')
    except Exception as e: st.error(f"Erreur d'écriture utilisateur : {e}")

def modifier_mot_de_passe_sheets(identifiant, nouveau_mdp):
    if not sh: return False
    try:
        ws = sh.worksheet("utilisateurs")
        cellule = ws.find(str(identifiant).strip().lower(), in_column=1)
        if cellule:
            ws.update_cell(cellule.row, 4, str(nouveau_mdp)) # Colonne 4 = mdp (D)
            return True
        return False
    except Exception as e:
        st.error(f"Erreur lors de la mise à jour du mot de passe dans Google Sheets : {e}")
        return False

def charger_plannings_sheets():
    if not sh: return PLANNINGS_PAR_DEFAUT
    try:
        ws = sh.worksheet("plannings")
        records = ws.get_all_records()
        if not records: return PLANNINGS_PAR_DEFAUT
        liste_plannings = []
        for r in records:
            participants = [p.strip().lower() for p in str(r["participants"]).split(",") if p.strip()]
            liste_plannings.append({
                "id": r["id"], "participants": participants, "date_debut": str(r["date_debut"]),
                "date_fin": str(r["date_fin"]), "lieu": r["lieu"], "tache": r["tache"], "statut": r["statut"]
            })
        return liste_plannings
    except Exception: return PLANNINGS_PAR_DEFAUT

def sauvegarder_planning_sheets(mission):
    if not sh: return
    try:
        ws = sh.worksheet("plannings")
        participants_str = ", ".join(mission["participants"])
        ws.append_row([mission["id"], participants_str, mission["date_debut"], mission["date_fin"], mission["lieu"], mission["tache"], mission["statut"]])
    except Exception as e: st.error(f"Erreur d'écriture planning : {e}")

def charger_rapports_sheets():
    if not sh: return []
    try:
        ws = sh.worksheet("rapports")
        return ws.get_all_records()
    except Exception: return []

def sauvegarder_rapport_sheets(rapport):
    if not sh: return
    try:
        ws = sh.worksheet("rapports")
        ws.append_row([rapport["employe"], rapport["date"], rapport["projet"], rapport["contenu"]])
    except Exception as e: st.error(f"Erreur d'écriture rapport : {e}")

# --- VALEURS PAR DÉFAUT ---
UTILISATEURS_PAR_DEFAUT = {
    "admin@entreprise.com": {"nom": "Admin", "role": "admin", "mdp": "admin123", "tel": "", "email_contact": "admin@entreprise.com"},    
    "sb@arhen.energy": {"nom": "Samir BOUABDELLAH", "role": "admin", "mdp": "hml73200!", "tel": "", "email_contact": "sb@arhen.energy"},
    "hasan.gozel@arhen.energy": {"nom": "Hasan GOZEL", "role": "admin", "mdp": "hml73200!", "tel": "", "email_contact": "hasan.gozel@arhen.energy"},
    "loic.arribert@arhen.energy": {"nom": "Loïc ARRIBERT", "role": "admin", "mdp": "hml73200!", "tel": "", "email_contact": "loic.arribert@arhen.energy"},
    "mc@arhen.energy": {"nom": "Marcia DE CASTRO", "role": "admin", "mdp": "hml73200!", "tel": "", "email_contact": "mc@arhen.energy"},
    "hy@arhen.energy": {"nom": "Hümeyra YILDIZ", "role": "admin", "mdp": "test123", "tel": "", "email_contact": "hy@arhen.energy"}
}

PLANNINGS_PAR_DEFAUT = [
    {"id": 1, "participants": ["sb@arhen.energy"], "date_debut": str(datetime.now().date()), "date_fin": str(datetime.now().date() + timedelta(days=2)), "lieu": "CHANTIER PARIS", "tache": "Installation des modules photovoltaïques", "statut": "Production"}
]

if "utilisateurs" not in st.session_state: st.session_state["utilisateurs"] = charger_utilisateurs_sheets()
if "plannings" not in st.session_state: st.session_state["plannings"] = charger_plannings_sheets()
if "rapports" not in st.session_state: st.session_state["rapports"] = charger_rapports_sheets()
if "date_calendrier" not in st.session_state: st.session_state["date_calendrier"] = datetime.now().date()

cookie_manager = stx.CookieManager()
COULEURS_STATUTS = {"Production": {"accent": "#0284C7"}, "Planifié": {"accent": "#059669"}, "Urgent": {"accent": "#DC2626"}}

saved_user = None
try:
    time.sleep(0.2)
    saved_user = cookie_manager.get(cookie="user_session")
except Exception: pass

if saved_user is None and "cookie_init" not in st.session_state:
    st.session_state["cookie_init"] = True
    st.stop()

if "user_connecte" not in st.session_state:
    if saved_user and saved_user in st.session_state["utilisateurs"]:
        st.session_state["user_connecte"] = {**st.session_state["utilisateurs"][saved_user], "identifiant": saved_user}
    else: st.session_state["user_connecte"] = None

# --- ÉCRAN D'ACCUEIL / AUTH ---
if st.session_state["user_connecte"] is None:
    onglet_auth = st.tabs(["Connexion", "Créer un compte"])
    
    with onglet_auth[0]:
        st.subheader("Connexion")
        type_connexion = st.radio("Se connecter avec :", ["Email", "Numéro de téléphone"], horizontal=True, key="type_conn")
        if type_connexion == "Email": identifiant_saisi = st.text_input("Adresse Email", key="login_email").strip().lower()
        else: identifiant_saisi = st.text_input("Numéro de téléphone", key="login_tel").strip()
        mdp_saisi = st.text_input("Mot de passe", type="password", key="login_mdp")
        if st.button("Se connecter", use_container_width=True):
            user_trouve, cle_user = None, None
            for key, infos in st.session_state["utilisateurs"].items():
                if type_connexion == "Email" and key == identifiant_saisi: user_trouve, cle_user = infos, key; break
                elif type_connexion == "Numéro de téléphone" and infos.get("tel") == identifiant_saisi: user_trouve, cle_user = infos, key; break
            if user_trouve and user_trouve["mdp"] == mdp_saisi:
                st.session_state["user_connecte"] = {**user_trouve, "identifiant": cle_user}
                cookie_manager.set("user_session", cle_user, max_age=2592000)
                st.success(f"Bienvenue {user_trouve['nom']} !")
                time.sleep(0.5); st.rerun()
            else: st.error("Identifiants ou mot de passe incorrects.")
            
    with onglet_auth[1]:
        st.subheader("Créer un compte")
        with st.form("form_inscription", clear_on_submit=True):
            nouvel_identifiant = st.text_input("Adresse Email").strip().lower()
            nouveau_nom = st.text_input("Nom et Prénom")
            nouveau_tel = st.text_input("Numéro de téléphone")
            nouveau_mdp = st.text_input("Choisissez un mot de passe", type="password")
            
            if st.form_submit_button("S'inscrire", use_container_width=True):
                if nouvel_identifiant and nouveau_nom and nouveau_mdp:
                    if nouvel_identifiant in st.session_state["utilisateurs"]:
                        st.error("Cet identifiant existe déjà.")
                    else:
                        infos_nouvel_user = {
                            "nom": nouveau_nom,
                            "role": "employe",
                            "mdp": nouveau_mdp,
                            "tel": nouveau_tel,
                            "email_contact": nouvel_identifiant
                        }
                        st.session_state["utilisateurs"][nouvel_identifiant] = infos_nouvel_user
                        sauvegarder_utilisateur_sheets(nouvel_identifiant, infos_nouvel_user)
                        
                        st.success("Compte créé avec succès ! Vous pouvez maintenant basculer sur l'onglet Connexion.")
                        time.sleep(1.5)
                        st.rerun()
                else:
                    st.error("Veuillez remplir tous les champs obligatoires (Email, Nom, Mot de passe).")
    st.stop()

user = st.session_state["user_connecte"]
user_key = user["identifiant"]

# --- CONFIGURATION DES DATES ---
date_active = st.session_state["date_calendrier"]
lundi_semaine = date_active - timedelta(days=date_active.weekday())
noms_jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
jours = [{"nom": noms_jours[i], "date_texte": (lundi_semaine + timedelta(days=i)).strftime('%d/%m'), "date_str": str(lundi_semaine + timedelta(days=i))} for i in range(7)]

# ==========================================
# BARRE LATÉRALE À GAUCHE (SIDEBAR)
# ==========================================
st.sidebar.markdown(f"{user['nom']}")

# Affichage visuel du rôle : UTILISATEUR au lieu de EMPLOYE
role_affiche = "ADMIN" if user["role"] == "admin" else "UTILISATEUR"
st.sidebar.markdown(f"**Rôle :** {role_affiche}")
st.sidebar.markdown("---")

# --- MODULE CHANGEMENT DE MOT DE PASSE (SIDEBAR) ---
with st.sidebar.expander("🔑 Changer mon mot de passe"):
    with st.form("form_changement_mdp", clear_on_submit=True):
        ancien_mdp = st.text_input("Ancien mot de passe", type="password")
        nouveau_mdp = st.text_input("Nouveau mot de passe", type="password")
        confirm_mdp = st.text_input("Confirmer le nouveau mot de passe", type="password")
        
        if st.form_submit_button("Modifier", use_container_width=True):
            if user["mdp"] != ancien_mdp:
                st.error("L'ancien mot de passe est incorrect.")
            elif not nouveau_mdp:
                st.warning("Veuillez saisir un mot de passe.")
            elif nouveau_mdp != confirm_mdp:
                st.error("Les mots de passe ne correspondent pas.")
            else:
                st.session_state["utilisateurs"][user_key]["mdp"] = nouveau_mdp
                st.session_state["user_connecte"]["mdp"] = nouveau_mdp
                
                if modifier_mot_de_passe_sheets(user_key, nouveau_mdp):
                    st.success("Mot de passe modifié avec succès !")
                else:
                    st.error("Erreur lors de la synchronisation.")

st.sidebar.markdown("---")

if user["role"] == "admin":
    liste_utilisateurs_choix = ["Tous les utilisateurs"] + list(st.session_state["utilisateurs"].keys())
    employe_filtre = st.sidebar.selectbox("Filtre pour le PDF :", options=liste_utilisateurs_choix, format_func=lambda x: "Tous les utilisateurs" if x == "Tous les utilisateurs" else st.session_state["utilisateurs"][x]["nom"], key="sidebar_emp_filtre")
else:
    employe_filtre = user_key

st.sidebar.markdown("### Téléchargement")
pdf_planning_data = generer_pdf_planning(jours, st.session_state["plannings"], st.session_state["utilisateurs"], employe_filtre)

# Nom dynamique du fichier PDF
nom_user_clean = "Tous" if employe_filtre == "Tous les utilisateurs" else st.session_state["utilisateurs"].get(employe_filtre, {}).get("nom", "Utilisateur").replace(" ", "_")
nom_fichier_pdf = f"Planning_{nom_user_clean}_{jours[0]['date_texte'].replace('/', '-')}.pdf"

st.sidebar.download_button(
    label="📅 Télécharger le Planning (PDF)",
    data=pdf_planning_data,
    file_name=nom_fichier_pdf,
    mime="application/pdf",
    use_container_width=True
)

st.sidebar.markdown("---")
if st.sidebar.button("Déconnexion", use_container_width=True):
    st.session_state["user_connecte"] = None
    try: cookie_manager.delete("user_session")
    except Exception: pass
    st.rerun()

# --- STYLES CSS ---
st.markdown("""
    <style>
    .header-jour { text-align: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid var(--text-color); }
    .nom-jour { margin: 0; font-size: 11px; opacity: 0.6; font-weight: 700; text-transform: uppercase; }
    .num-jour { margin: 4px 0 0 0; font-size: 22px; font-weight: 800; }
    .shift-card-container { border-radius: 8px; background-color: var(--background-color); border: 1px solid rgba(128, 128, 128, 0.2); border-left: 5px solid #64748B; padding: 12px; margin-bottom: 8px; }
    .shift-lieu { margin: 0; font-size: 12px; font-weight: 700; text-transform: uppercase; }
    .shift-team { margin: 4px 0 6px 0; font-size: 11px; color: #0284C7; font-style: italic; }
    .shift-task { margin: 0; font-size: 12px; opacity: 0.9; white-space: pre-wrap; }
    </style>
""", unsafe_allow_html=True)

if user["role"] == "admin": onglet_actif = st.tabs(["Calendrier", "Planifier", "Rapports Reçus", "Gestion des Comptes"])
else: onglet_actif = st.tabs(["Calendrier", "Envoyer un Rapport"])

# ==========================================
# ONGLET 1 : CALENDRIER
# ==========================================
with onglet_actif[0]:
    st.markdown("<h2 style='margin: 0 0 15px 0;'>Calendrier de la semaine</h2>", unsafe_allow_html=True)
    
    col_date, col_filtre_affichage = st.columns([3, 3])
    with col_date:
        st.date_input("Sélection de la date", key="date_calendrier", format="DD/MM/YYYY")
    with col_filtre_affichage:
        if user["role"] == "admin":
            liste_affichage = ["Tous les utilisateurs"] + list(st.session_state["utilisateurs"].keys())
            employe_affichage = st.selectbox("Filtrer l'affichage écran :", options=liste_affichage, format_func=lambda x: "Tous les utilisateurs" if x == "Tous les utilisateurs" else st.session_state["utilisateurs"][x]["nom"], key="screen_emp_filtre")
        else: employe_affichage = user_key

    cols = st.columns(7)
    for i, jour in enumerate(jours):
        current_date = datetime.strptime(jour["date_str"], "%Y-%m-%d").date()
        with cols[i]:
            st.markdown(f'<div class="header-jour"><p class="nom-jour">{jour["nom"]}</p><p class="num-jour">{jour["date_texte"]}</p></div>', unsafe_allow_html=True)
            shifts_du_jour = []
            for s in st.session_state["plannings"]:
                if not s.get("date_debut"): continue
                try:
                    if datetime.strptime(str(s["date_debut"]), "%Y-%m-%d").date() <= current_date <= datetime.strptime(str(s["date_fin"]), "%Y-%m-%d").date():
                        emp_aff_clean = employe_affichage.strip().lower() if employe_affichage != "Tous les utilisateurs" else "Tous les utilisateurs"
                        participants_clean = [str(p).strip().lower() for p in s.get("participants", [])]
                        if emp_aff_clean == "Tous les utilisateurs" or emp_aff_clean in participants_clean: shifts_du_jour.append(s)
                except: continue
            
            if shifts_du_jour:
                for s in shifts_du_jour:
                    statut_style = COULEURS_STATUTS.get(s.get("statut", "Planifié"), {"accent": "#64748B"})
                    noms_equipe = ", ".join([st.session_state["utilisateurs"][emp]["nom"] for emp in s.get("participants", []) if emp in st.session_state["utilisateurs"]])
                    st.markdown(f'<div class="shift-card-container" style="border-left-color: {statut_style["accent"]};"><p class="shift-lieu">{s["lieu"]}</p><p class="shift-team">Équipe : {noms_equipe if noms_equipe else "Aucune"}</p><p class="shift-task">{s["tache"]}</p></div>', unsafe_allow_html=True)
            else: st.markdown("<p style='text-align: center; opacity: 0.3; font-size: 12px;'>Aucun chantier</p>", unsafe_allow_html=True)

# ==========================================
# CÔTÉ ADMIN - ENREGISTREMENT ET NOTIFICATIONS PAR MAIL
# ==========================================
if user["role"] == "admin":
    with onglet_actif[1]:
        st.markdown("<h2>Planifier une Mission</h2>", unsafe_allow_html=True)
        with st.form("form_centre_shift", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                equipe_sel = st.multiselect("Équipe affectée", options=list(st.session_state["utilisateurs"].keys()), format_func=lambda x: st.session_state["utilisateurs"][x]["nom"])
                date_debut_sel = st.date_input("Date de DÉBUT", datetime.now().date())
                date_fin_sel = st.date_input("Date de FIN", datetime.now().date())
            with col2:
                lieu_input = st.text_input("Lieu ou Nom du projet")
                statut_selection = st.selectbox("Statut", ["Production", "Planifié", "Urgent"])
            tache_input = st.text_area("Descriptif")
            
            if st.form_submit_button("Planifier", use_container_width=True):
                if equipe_sel and lieu_input and tache_input:
                    nouvelle_mission = {"id": int(time.time()), "participants": [p.strip().lower() for p in equipe_sel], "date_debut": str(date_debut_sel), "date_fin": str(date_fin_sel), "lieu": lieu_input.upper(), "tache": tache_input, "statut": statut_selection}
                    st.session_state["plannings"].append(nouvelle_mission)
                    sauvegarder_planning_sheets(nouvelle_mission)
                    
                    for emp_key in equipe_sel:
                        infos_employe = st.session_state["utilisateurs"].get(emp_key, {})
                        email_destinataire = infos_employe.get("email_contact", "").strip()
                        
                        if not email_destinataire and "@" in emp_key:
                            email_destinataire = emp_key
                            
                        if "@" in email_destinataire:
                            corps_mail = f"""
                            <h3>Bonjour {infos_employe.get('nom', 'Utilisateur')},</h3>
                            <p>Une nouvelle mission vient de vous être assignée sur le planning :</p>
                            <ul>
                                <li><b>Lieu / Projet :</b> {lieu_input.upper()}</li>
                                <li><b>Période :</b> Du {date_debut_sel.strftime('%d/%m/%Y')} au {date_fin_sel.strftime('%d/%m/%Y')}</li>
                                <li><b>Statut :</b> {statut_selection}</li>
                                <li><b>Description :</b> {tache_input}</li>
                            </ul>
                            <p>Connectez-vous sur l'application pour consulter votre calendrier complet.</p>
                            """
                            envoyer_notification_email(email_destinataire, f"[Planning] Nouvelle affectation : {lieu_input.upper()}", corps_mail)
                            
                    st.success("Mission synchronisée et notifications e-mails envoyées !")
                    time.sleep(0.5); st.rerun()

    with onglet_actif[2]:
        st.markdown("<h2>Rapports Chantiers Reçus</h2>", unsafe_allow_html=True)
        if st.session_state["rapports"]:
            for idx, r in enumerate(st.session_state["rapports"]):
                with st.expander(f"Rapport de {r.get('employe', 'Inconnu')} — {r.get('date', '')} ({r.get('projet', '')})"):
                    st.write(f"**Lieu/Projet :** {r.get('projet', '')}")
                    st.info(r.get('contenu', ''))
                    pdf_data = generer_pdf_rapport(r)
                    st.download_button(label="📥 Télécharger ce rapport en PDF", data=pdf_data, file_name=f"Rapport_{r.get('projet', 'chantier')}.pdf", mime="application/pdf", key=f"btn_pdf_{idx}")
        else: st.info("Aucun rapport reçu.")

    with onglet_actif[3]:
        st.markdown("<h2>Gestion des Comptes</h2>", unsafe_allow_html=True)
        liste_comptes = [{"Nom complet": infos["nom"], "Identifiant": idf, "Téléphone": infos.get("tel",""), "Rôle": "ADMIN" if infos["role"] == "admin" else "UTILISATEUR"} for idf, infos in st.session_state["utilisateurs"].items()]
        st.dataframe(pd.DataFrame(liste_comptes), use_container_width=True, hide_index=True)

# ==========================================
# CÔTÉ UTILISATEUR NON-ADMIN - ENVOI DE RAPPORT
# ==========================================
else:
    with onglet_actif[1]:
        st.markdown("<h2>Envoyer un Rapport d'Activité</h2>", unsafe_allow_html=True)
        with st.form("form_rapport_employe", clear_on_submit=True):
            projet_nom = st.text_input("Nom du chantier / Lieu")
            rapport_texte = st.text_area("Détails de l'avancement")
            
            if st.form_submit_button("Envoyer le rapport", use_container_width=True):
                if projet_nom and rapport_texte:
                    date_now_str = datetime.now().strftime("%d/%m/%Y à %H:%M")
                    nouveau_rapport = {"employe": user["nom"], "date": date_now_str, "projet": projet_nom.upper(), "contenu": rapport_texte}
                    st.session_state["rapports"].append(nouveau_rapport)
                    sauvegarder_rapport_sheets(nouveau_rapport)
                    
                    admin_principal = "appli.planning0@gmail.com"
                    corps_admin_mail = f"""
                    <h3>Nouveau rapport d'activité reçu</h3>
                    <p><b>Utilisateur :</b> {user["nom"]}</p>
                    <p><b>Chantier / Projet :</b> {projet_nom.upper()}</p>
                    <p><b>Date d'envoi :</b> {date_now_str}</p>
                    <hr/>
                    <p><b>Contenu du rapport :</b></p>
                    <p style="background-color: #f3f4f6; padding: 10px; border-left: 4px solid #0284C7;">{rapport_texte.replace('\n', '<br/>')}</p>
                    <p>Vous pouvez télécharger la version PDF officielle directement depuis votre espace administrateur.</p>
                    """
                    envoyer_notification_email(admin_principal, f"[Rapport Reçu] {user['nom']} - {projet_nom.upper()}", corps_admin_mail)
                    
                    st.success("Rapport transmis et enregistré !")
                    time.sleep(0.5); st.rerun()
