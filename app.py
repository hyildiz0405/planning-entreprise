import streamlit as st
from datetime import datetime, timedelta
import calendar
import extra_streamlit_components as stx
import json
import time
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from io import BytesIO

# Éléments requis pour le PDF
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURATION INITIALE DE L'APPLICATION ---
st.set_page_config(page_title="Planning Entreprise", page_icon="logo.png", layout="wide")

# --- COMPTES UTILISATEURS MIS À JOUR ---
UTILISATEURS = {
    "admin@entreprise.com": {"nom": "Admin", "role": "admin", "mdp": "admin123"},    
    "sb@arhen.energy": {"nom": "Samir BOUABDELLAH", "role": "admin", "mdp": "hml73200!"},
    "hasan.gozel@arhen.energy": {"nom": "Hasan GOZEL", "role": "admin", "mdp": "hml73200!"},
    "loic.arribert@arhen.energy": {"nom": "Loïc ARRIBERT", "role": "admin", "mdp": "hml73200!"},
    "mc@arhen.energy": {"nom": "Marcia DE CASTRO", "role": "admin", "mdp": "hml73200!"},
    "hy@arhen.energy": {"nom": "Hümeyra YILDIZ", "role": "admin", "mdp": "test123"}
}

if "utilisateurs" not in st.session_state:
    st.session_state["utilisateurs"] = UTILISATEURS

# --- CONNEXION GOOGLE SHEETS EN DIRECT ---
URL_SHEET = "https://docs.google.com/spreadsheets/d/1nIiT1ql3mL4VmcBuLlST8QD0QKItAHq72B9P0THH-ns/edit?usp=sharing"

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_plannings = conn.read(spreadsheet=URL_SHEET, ttl=5)
    st.session_state["plannings"] = df_plannings.to_dict(orient="records")
    for s in st.session_state["plannings"]:
        if isinstance(s.get("participants"), str):
            try:
                s["participants"] = json.loads(s["participants"].replace("'", '"'))
            except:
                s["participants"] = [s["participants"]]
except Exception as e:
    st.session_state["plannings"] = []

if "rapports" not in st.session_state:
    st.session_state["rapports"] = []

if "date_calendrier" not in st.session_state:
    st.session_state["date_calendrier"] = datetime.now().date()

# --- GESTIONNAIRE DE COOKIES ---
cookie_manager = stx.CookieManager()

COULEURS_STATUTS = {
    "Production": {"accent": "#0284C7"},
    "Planifié": {"accent": "#059669"},
    "Urgent": {"accent": "#DC2626"}
}

# --- GESTION DE LA SESSION ---
saved_user = None
try:
    time.sleep(0.2)
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

if st.session_state["user_connecte"] is None:
    st.subheader("Connexion")
    email_saisi = st.text_input("Adresse Email")
    mdp_saisi = st.text_input("Mot de passe", type="password")
    
    if st.button("Se connecter", use_container_width=True):
        if email_saisi in st.session_state["utilisateurs"] and st.session_state["utilisateurs"][email_saisi]["mdp"] == mdp_saisi:
            st.session_state["user_connecte"] = {**st.session_state["utilisateurs"][email_saisi], "email": email_saisi}
            cookie_manager.set("user_session", email_saisi, max_age=2592000)
            st.rerun()
        else:
            st.error("Identifiants incorrects.")
    st.stop()

# --- CONFIGURATION DES DATES ---
date_active = st.session_state["date_calendrier"]
lundi_semaine = date_active - timedelta(days=date_active.weekday())
dimanche_semaine = lundi_semaine + timedelta(days=6)

noms_jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
jours = []
for i in range(7):
    j = lundi_semaine + timedelta(days=i)
    jours.append({"nom": noms_jours[i], "date_texte": j.strftime('%d/%m'), "date_str": str(j)})

# --- FONCTION DE GÉNÉRATION DU PDF ---
def generer_pdf_global(liste_missions):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=15, leftMargin=15, topMargin=20, bottomMargin=20)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor("#0F172A"), alignment=0)
    header_style = ParagraphStyle('HeaderTable', fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=colors.white, alignment=1)
    cell_style = ParagraphStyle('CellTable', fontName="Helvetica", fontSize=8, leading=11, textColor=colors.HexColor("#1E293B"))
    cell_bold = ParagraphStyle('CellBold', fontName="Helvetica-Bold", fontSize=8, leading=11, textColor=colors.HexColor("#0F172A"))
    
    titre = f"RAPPORT DE PLANNING GENERAL — SEMAINE DU {lundi_semaine.strftime('%d/%m/%Y')} AU {dimanche_semaine.strftime('%d/%m/%Y')}"
    story.append(Paragraph(titre, title_style))
    story.append(Spacer(1, 15))
    
    headers = [
        Paragraph("<b>Lieu</b>", header_style),
        Paragraph("<b>Objet / Mission</b>", header_style),
        Paragraph("<b>Début</b>", header_style),
        Paragraph("<b>Fin</b>", header_style),
        Paragraph("<b>Participants</b>", header_style),
        Paragraph("<b>Statut</b>", header_style)
    ]
    
    table_data = [headers]
    
    for s in liste_missions:
        noms_equipe = ", ".join([st.session_state["utilisateurs"][emp]["nom"] for emp in s.get("participants", []) if emp in st.session_state["utilisateurs"]])
        tache_propre = str(s['tache']).replace('\n', '<br/>')
        
        str_deb = s.get("date_debut")
        str_fin = s.get("date_fin")
        
        d_deb = datetime.strptime(str(str_deb), "%Y-%m-%d").strftime("%d/%m/%Y") if str_deb and not pd.isna(str_deb) else "—"
        d_fin = datetime.strptime(str(str_fin), "%Y-%m-%d").strftime("%d/%m/%Y") if str_fin and not pd.isna(str_fin) else "—"
        
        table_data.append([
            Paragraph(str(s['lieu']), cell_bold),
            Paragraph(tache_propre, cell_style),
            Paragraph(d_deb, cell_style),
            Paragraph(d_fin, cell_style),
            Paragraph(noms_equipe, cell_style),
            Paragraph(str(s.get('statut', 'Planifié')), cell_bold)
        ])
        
    t = Table(table_data, colWidths=[110, 292, 80, 80, 140, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer

employe_filtre = st.session_state.get("emp_filtre_key", "Tous les employés")
user = st.session_state["user_connecte"]
if user["role"] != "admin":
    employe_filtre = user["email"]

# Filtrer les missions de la semaine pour le PDF
missions_semaine = []
for s in st.session_state["plannings"]:
    str_deb = s.get("date_debut")
    str_fin = s.get("date_fin")
    if not str_deb or not str_fin or pd.isna(str_deb) or pd.isna(str_fin):
        continue
    try:
        deb_s = datetime.strptime(str(str_deb), "%Y-%m-%d").date()
        fin_s = datetime.strptime(str(str_fin), "%Y-%m-%d").date()
        if not (fin_s < lundi_semaine or deb_s > dimanche_semaine):
            if employe_filtre == "Tous les employés" or employe_filtre in s.get("participants", []):
                missions_semaine.append(s)
    except:
        continue

# --- BARRE LATÉRALE ---
st.sidebar.markdown(f"### Utilisateur : {user['nom']}")
st.sidebar.markdown(f"**Rôle système :** {user['role'].upper()}")
st.sidebar.markdown("---")

# Bouton PDF réactivé si des chantiers existent cette semaine
if missions_semaine:
    try:
        pdf_data = generer_pdf_global(missions_semaine)
        st.sidebar.download_button(
            label="Télécharger le planning (PDF)",
            data=pdf_data,
            file_name=f"planning_semaine_{lundi_semaine.strftime('%d_%m_%Y')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    except Exception as e:
        st.sidebar.error("Erreur de préparation du PDF.")

if st.sidebar.button("Déconnexion", use_container_width=True):
    st.session_state["user_connecte"] = None
    try: cookie_manager.delete("user_session")
    except Exception: pass
    st.rerun()

# --- CSS STYLES ---
st.markdown("""
    <style>
    .header-jour { text-align: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid var(--text-color); }
    .nom-jour { margin: 0; font-size: 11px; opacity: 0.6; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
    .num-jour { margin: 4px 0 0 0; font-size: 22px; font-weight: 800; }
    .shift-card-container { 
        border-radius: 8px; 
        background-color: var(--background-color);
        background-image: linear-gradient(rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.05));
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-left: 5px solid #64748B; 
        padding: 12px; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); 
        margin-bottom: 8px; 
    }
    .shift-lieu { margin: 0; font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--text-color); }
    .shift-team { margin: 4px 0 6px 0; font-size: 11px; color: #0284C7; font-style: italic; font-weight: 600; }
    .shift-task { margin: 0; font-size: 12px; color: var(--text-color); opacity: 0.9; white-space: pre-wrap; word-break: break-word; line-height: 1.4; }
    </style>
""", unsafe_allow_html=True)

# Configuration dynamique des onglets
if user["role"] == "admin":
    onglet_actif = st.tabs(["Calendrier", "Planifier", "Rapports Reçus", "Gestion des Comptes"])
else:
    onglet_actif = st.tabs(["Calendrier", "Envoyer un Rapport"])

# ==========================================
# ONGLET 1 : CALENDRIER
# ==========================================
with onglet_actif[0]:
    st.markdown("<h2 style='margin: 0 0 15px 0;'>Calendrier</h2>", unsafe_allow_html=True)
    col_date, col_filtre = st.columns(2)
    with col_date:
        st.date_input("Sélection de la date", key="date_calendrier", format="DD/MM/YYYY")
    with col_filtre:
        liste_employes_choix = ["Tous les employés"] + list(st.session_state["utilisateurs"].keys())
        def formater_nom_filtre(x):
            if x == "Tous les employés": return "Tous les employés"
            return st.session_state["utilisateurs"][x]["nom"]
        if user["role"] == "admin":
            st.selectbox("Filtrer par employé", options=liste_employes_choix, format_func=formater_nom_filtre, key="emp_filtre_key")
        else:
            st.session_state["emp_filtre_key"] = user["email"]

    cols = st.columns(7)
    for i, jour in enumerate(jours):
        current_date = datetime.strptime(jour["date_str"], "%Y-%m-%d").date()
        with cols[i]:
            st.markdown(f'<div class="header-jour"><p class="nom-jour">{jour["nom"]}</p><p class="num-jour">{jour["date_texte"]}</p></div>', unsafe_allow_html=True)
            
            shifts_du_jour = []
            for s in st.session_state["plannings"]:
                if not s.get("date_debut") or pd.isna(s.get("date_debut")): continue
                try:
                    d_deb = datetime.strptime(str(s["date_debut"]), "%Y-%m-%d").date()
                    d_fin = datetime.strptime(str(s["date_fin"]), "%Y-%m-%d").date()
                    if d_deb <= current_date <= d_fin:
                        if employe_filtre == "Tous les employés" or employe_filtre in s.get("participants", []):
                            shifts_du_jour.append(s)
                except:
                    continue
            
            if shifts_du_jour:
                for s in shifts_du_jour:
                    statut_style = COULEURS_STATUTS.get(s.get("statut", "Planifié"), {"accent": "#64748B"})
                    noms_equipe = ", ".join([st.session_state["utilisateurs"][emp]["nom"] for emp in s.get("participants", []) if emp in st.session_state["utilisateurs"]])
                    
                    st.markdown(f"""
                        <div class="shift-card-container" style="border-left-color: {statut_style["accent"]};">
                            <p class="shift-lieu">{s["lieu"]}</p>
                            <p class="shift-team">Équipe : {noms_equipe if noms_equipe else "Aucune"}</p>
                            <p class="shift-task">{s["tache"]}</p>
                        </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("<p style='text-align: center; opacity: 0.3; font-size: 12px;'>Aucun chantier</p>", unsafe_allow_html=True)

# ==========================================
# CÔTÉ ADMIN - ONGLET 2 : PLANIFIER
# ==========================================
if user["role"] == "admin":
    with onglet_actif[1]:
        st.markdown("<h2 style='margin: 0 0 15px 0;'>Planifier une Mission</h2>", unsafe_allow_html=True)
        with st.form("form_centre_shift", clear_on_submit=True):
            col_1, col_2 = st.columns(2)
            with col_1:
                equipe_sel = st.multiselect("Équipe", options=list(st.session_state["utilisateurs"].keys()), format_func=lambda x: st.session_state["utilisateurs"][x]["nom"])
                date_debut_sel = st.date_input("Date de DÉBUT", datetime.now().date(), format="DD/MM/YYYY")
                date_fin_sel = st.date_input("Date de FIN", datetime.now().date(), format="DD/MM/YYYY")
            with col_2:
                lieu_input = st.text_input("Lieu ou Nom du projet")
                statut_selection = st.selectbox("Statut", ["Production", "Planifié", "Urgent"])
            tache_input = st.text_area("Descriptif")
            
            if st.form_submit_button("Planifier", use_container_width=True):
                if equipe_sel and lieu_input and tache_input:
                    nouvel_id = int(time.time())
                    
                    nouvelle_mission = pd.DataFrame([{
                        "id": nouvel_id,
                        "participants": json.dumps(equipe_sel),
                        "date_debut": str(date_debut_sel),
                        "date_fin": str(date_fin_sel),
                        "lieu": lieu_input.upper(),
                        "tache": tache_input,
                        "statut": statut_selection
                    }])
                    
                    try:
                        df_existant = conn.read(spreadsheet=URL_SHEET, ttl=0)
                        df_total = pd.concat([df_existant, nouvelle_mission], ignore_index=True)
                        conn.update(spreadsheet=URL_SHEET, data=df_total)
                        st.toast("Mission enregistrée à vie sur Google Sheet !")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur d'écriture sur Google Sheet : {e}")

    # ==========================================
    # CÔTÉ ADMIN - ONGLET 3 : RAPPORTS REÇUS (CONTENU AJOUTÉ)
    # ==========================================
    with onglet_actif[2]:
        st.markdown("<h2 style='margin: 0 0 15px 0;'>Rapports Chantiers Reçus</h2>", unsafe_allow_html=True)
        st.info("Aucun rapport d'activité n'a été soumis par les employés pour le moment.")

    # ==========================================
    # CÔTÉ ADMIN - ONGLET 4 : GESTION DES COMPTES
    # ==========================================
    with onglet_actif[3]:
        st.markdown("<h2 style='margin: 0 0 15px 0;'>Gestion des Comptes Utilisateurs</h2>", unsafe_allow_html=True)
        st.markdown("Voici la liste complète des comptes configurés dans l'application avec leurs accès.")
        
        liste_comptes = []
        for email, infos in st.session_state["utilisateurs"].items():
            liste_comptes.append({
                "Nom complet": infos["nom"],
                "Adresse Email": email,
                "Rôle": infos["role"].upper(),
                "Mot de passe": infos["mdp"]
            })
        
        df_comptes = pd.DataFrame(liste_comptes)
        st.dataframe(df_comptes, use_container_width=True, hide_index=True)
