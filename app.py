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

# --- CONFIGURATION INITIALE DE L'APPLICATION ---
st.set_page_config(page_title="Planning Entreprise", page_icon="logo.png", layout="wide")

# --- CONNEXION À GOOGLE SHEETS ---
NOM_DU_SHEET = "Planning Arhen Data"  # /!\ Change par le nom exact de ton Google Sheet
FICHIER_CLE_JSON = "arhen-planning-e680822dc074.json"

@st.cache_resource
def initialiser_gspread():
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        # Chargement des identifiants depuis le fichier fourni
        creds = Credentials.from_service_account_file(FICHIER_CLE_JSON, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open(NOM_DU_SHEET)
    except Exception as e:
        st.error(f"Erreur de connexion à Google Sheets : {e}")
        return None

sh = initialiser_gspread()

# --- FONCTIONS DE SAUVEGARDE ET CHARGEMENT VIA GOOGLE SHEETS ---
def charger_utilisateurs_sheets():
    if not sh: return UTILISATEURS_PAR_DEFAUT
    try:
        ws = sh.worksheet("utilisateurs")
        records = ws.get_all_records()
        if not records: return UTILISATEURS_PAR_DEFAUT
        
        users_dict = {}
        for r in records:
            users_dict[str(r["identifiant"])] = {
                "nom": r["nom"],
                "role": r["role"],
                "mdp": str(r["mdp"]),
                "tel": str(r["tel"]),
                "email_contact": r["email_contact"]
            }
        return users_dict
    except Exception:
        return UTILISATEURS_PAR_DEFAUT

def sauvegarder_utilisateur_sheets(identifiant, infos):
    if not sh: return
    try:
        ws = sh.worksheet("utilisateurs")
        # On ajoute simplement une nouvelle ligne
        ws.append_row([identifiant, infos["nom"], infos["role"], infos["mdp"], infos["tel"], infos["email_contact"]])
    except Exception as e:
        st.error(f"Erreur d'écriture utilisateur dans Google Sheets : {e}")

def charger_plannings_sheets():
    if not sh: return PLANNINGS_PAR_DEFAUT
    try:
        ws = sh.worksheet("plannings")
        records = ws.get_all_records()
        if not records: return PLANNINGS_PAR_DEFAUT
        
        liste_plannings = []
        for r in records:
            # Les participants sont stockés sous forme de texte séparé par des virgules
            participants = [p.strip() for p in str(r["participants"]).split(",") if p.strip()]
            liste_plannings.append({
                "id": r["id"],
                "participants": participants,
                "date_debut": str(r["date_debut"]),
                "date_fin": str(r["date_fin"]),
                "lieu": r["lieu"],
                "tache": r["tache"],
                "statut": r["statut"]
            })
        return liste_plannings
    except Exception:
        return PLANNINGS_PAR_DEFAUT

def sauvegarder_planning_sheets(mission):
    if not sh: return
    try:
        ws = sh.worksheet("plannings")
        participants_str = ", ".join(mission["participants"])
        ws.append_row([mission["id"], participants_str, mission["date_debut"], mission["date_fin"], mission["lieu"], mission["tache"], mission["statut"]])
    except Exception as e:
        st.error(f"Erreur d'écriture planning dans Google Sheets : {e}")

def charger_rapports_sheets():
    if not sh: return []
    try:
        ws = sh.worksheet("rapports")
        records = ws.get_all_records()
        return records
    except Exception:
        return []

def sauvegarder_rapport_sheets(rapport):
    if not sh: return
    try:
        ws = sh.worksheet("rapports")
        ws.append_row([rapport["employe"], rapport["date"], rapport["projet"], rapport["contenu"]])
    except Exception as e:
        st.error(f"Erreur d'écriture rapport dans Google Sheets : {e}")

# --- CONFIGURATION CONFIGURATION SMTP ---
SMTP_SERVEUR = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_EXPEDITEUR = "votre_email_notif@gmail.com"
SMTP_MOT_DE_PASSE = "votre_mot_de_passe_application" 

# --- FONCTION D'ENVOI D'EMAIL ---
def envoyer_email_notification(destinataire, sujet, message_corps):
    if not destinataire or "@" not in destinataire:
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EXPEDITEUR
        msg['To'] = destinataire
        msg['Subject'] = sujet
        msg.attach(MIMEText(message_corps, 'plain', 'utf-8'))
        
        server = smtplib.SMTP_SSL(SMTP_SERVEUR, SMTP_PORT)
        server.login(SMTP_EXPEDITEUR, SMTP_MOT_DE_PASSE)
        server.sendmail(SMTP_EXPEDITEUR, destinataire, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Erreur d'envoi email à {destinataire} : {e}")
        return False

# --- VALEURS PAR DÉFAUT SI LE GOOGLE SHEET EST VIDE ---
UTILISATEURS_PAR_DEFAUT = {
    "admin@entreprise.com": {"nom": "Admin", "role": "admin", "mdp": "admin123", "tel": "", "email_contact": "admin@entreprise.com"},    
    "sb@arhen.energy": {"nom": "Samir BOUABDELLAH", "role": "admin", "mdp": "hml73200!", "tel": "0601020304", "email_contact": "sb@arhen.energy"}
}

PLANNINGS_PAR_DEFAUT = [
    {
        "id": 1,
        "participants": ["sb@arhen.energy"],
        "date_debut": str(datetime.now().date()),
        "date_fin": str(datetime.now().date() + timedelta(days=2)),
        "lieu": "CHANTIER PARIS",
        "tache": "Installation des modules photovoltaïques",
        "statut": "Production"
    }
]

# --- SYNCHRONISATION INITIALE DE LA SESSION ---
if "utilisateurs" not in st.session_state:
    st.session_state["utilisateurs"] = charger_utilisateurs_sheets()

if "plannings" not in st.session_state:
    st.session_state["plannings"] = charger_plannings_sheets()

if "rapports" not in st.session_state:
    st.session_state["rapports"] = charger_rapports_sheets()

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
        st.session_state["user_connecte"] = {**st.session_state["utilisateurs"][saved_user], "identifiant": saved_user}
    else:
        st.session_state["user_connecte"] = None

# --- ÉCRAN D'ACCUEIL ---
if st.session_state["user_connecte"] is None:
    onglet_auth = st.tabs(["Connexion", "Créer un compte"])
    
    with onglet_auth[0]:
        st.subheader("Connexion")
        type_connexion = st.radio("Se connecter avec :", ["Email", "Numéro de téléphone"], horizontal=True, key="type_conn")
        
        if type_connexion == "Email":
            identifiant_saisi = st.text_input("Adresse Email", key="login_email").strip().lower()
        else:
            identifiant_saisi = st.text_input("Numéro de téléphone (ex: 0612345678)", key="login_tel").strip()
            
        mdp_saisi = st.text_input("Mot de passe", type="password", key="login_mdp")
        
        if st.button("Se connecter", use_container_width=True):
            user_trouve = None
            cle_user = None
            
            for key, infos in st.session_state["utilisateurs"].items():
                if type_connexion == "Email" and key == identifiant_saisi:
                    user_trouve = infos
                    cle_user = key
                    break
                elif type_connexion == "Numéro de téléphone" and infos.get("tel") == identifiant_saisi:
                    user_trouve = infos
                    cle_user = key
                    break
            
            if user_trouve and user_trouve["mdp"] == mdp_saisi:
                st.session_state["user_connecte"] = {**user_trouve, "identifiant": cle_user}
                cookie_manager.set("user_session", cle_user, max_age=2592000)
                st.success(f"Bienvenue {user_trouve['nom']} !")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Identifiants ou mot de passe incorrects.")
                
    with onglet_auth[1]:
        st.subheader("Créer un nouveau compte")
        nom_neuf = st.text_input("Nom et Prénom")
        type_crea = st.radio("Identifiant principal :", ["Email", "Numéro de téléphone"], horizontal=True, key="type_crea")
        
        email_neuf = ""
        tel_neuf = ""
        
        if type_crea == "Email":
            email_neuf = st.text_input("Adresse Email (servira d'identifiant)").strip().lower()
            tel_neuf = st.text_input("Numéro de téléphone (Optionnel)").strip()
        else:
            tel_neuf = st.text_input("Numéro de téléphone (servira d'identifiant)").strip()
            email_neuf = st.text_input("Adresse Email (Optionnel)").strip().lower()
            
        mdp_neuf = st.text_input("Définir un mot de passe", type="password")
        
        if st.button("Créer mon compte", use_container_width=True):
            if not nom_neuf or not mdp_neuf:
                st.error("Veuillez remplir le nom et le mot de passe.")
            elif type_crea == "Email" and not email_neuf:
                st.error("Veuillez renseigner une adresse email valide.")
            elif type_crea == "Numéro de téléphone" and not tel_neuf:
                st.error("Veuillez renseigner un numéro de téléphone valide.")
            else:
                cle_creation = email_neuf if email_neuf else tel_neuf
                
                if cle_creation in st.session_state["utilisateurs"]:
                    st.error("Cet identifiant est déjà utilisé par un autre compte.")
                else:
                    nouvel_user = {
                        "nom": nom_neuf,
                        "role": "employe",
                        "mdp": mdp_neuf,
                        "tel": tel_neuf,
                        "email_contact": email_neuf
                    }
                    st.session_state["utilisateurs"][cle_creation] = nouvel_user
                    
                    # SAUVEGARDE GOOGLE SHEETS
                    sauvegarder_utilisateur_sheets(cle_creation, nouvel_user)
                    st.success("Compte créé avec succès ! Enregistré dans Google Sheets.")
    st.stop()

user = st.session_state["user_connecte"]
user_key = user["identifiant"]

# --- CONFIGURATION DES DATES ---
date_active = st.session_state["date_calendrier"]
lundi_semaine = date_active - timedelta(days=date_active.weekday())
dimanche_semaine = lundi_semaine + timedelta(days=6)

noms_jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
jours = []
for i in range(7):
    j = lundi_semaine + timedelta(days=i)
    jours.append({"nom": noms_jours[i], "date_texte": j.strftime('%d/%m'), "date_str": str(j)})

# --- BARRE LATÉRALE ---
st.sidebar.markdown(f"### Utilisateur : {user['nom']}")
st.sidebar.markdown(f"**Rôle système :** {user['role'].upper()}")
st.sidebar.markdown("---")

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
        if user["role"] == "admin":
            liste_employes_choix = ["Tous les employés"] + list(st.session_state["utilisateurs"].keys())
            def formater_nom_filtre(x):
                if x == "Tous les employés": return "Tous les employés"
                return st.session_state["utilisateurs"][x]["nom"]
            employe_filtre = st.selectbox("Filtrer par employé", options=liste_employes_choix, format_func=formater_nom_filtre, key="emp_filtre_key")
        else:
            employe_filtre = user_key

    cols = st.columns(7)
    for i, jour in enumerate(jours):
        current_date = datetime.strptime(jour["date_str"], "%Y-%m-%d").date()
        with cols[i]:
            st.markdown(f'<div class="header-jour"><p class="nom-jour">{jour["nom"]}</p><p class="num-jour">{jour["date_texte"]}</p></div>', unsafe_allow_html=True)
            
            shifts_du_jour = []
            for s in st.session_state["plannings"]:
                if not s.get("date_debut"): continue
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
                equipe_sel = st.multiselect("Équipe affectée", options=list(st.session_state["utilisateurs"].keys()), format_func=lambda x: st.session_state["utilisateurs"][x]["nom"])
                date_debut_sel = st.date_input("Date de DÉBUT", datetime.now().date(), format="DD/MM/YYYY")
                date_fin_sel = st.date_input("Date de FIN", datetime.now().date(), format="DD/MM/YYYY")
            with col_2:
                lieu_input = st.text_input("Lieu ou Nom du projet")
                statut_selection = st.selectbox("Statut", ["Production", "Planifié", "Urgent"])
            tache_input = st.text_area("Descriptif")
            
            if st.form_submit_button("Planifier", use_container_width=True):
                if equipe_sel and lieu_input and tache_input:
                    nouvel_id = int(time.time())
                    nouvelle_mission = {
                        "id": nouvel_id,
                        "participants": equipe_sel,
                        "date_debut": str(date_debut_sel),
                        "date_fin": str(date_fin_sel),
                        "lieu": lieu_input.upper(),
                        "tache": tache_input,
                        "statut": statut_selection
                    }
                    st.session_state["plannings"].append(nouvelle_mission)
                    
                    # SAUVEGARDE GOOGLE SHEETS
                    sauvegarder_planning_sheets(nouvelle_mission)
                    
                    # --- EMAILS DE NOTIFICATION ---
                    compteur_mails = 0
                    sujet_mail = f"[PLANNING ARHEN] Nouvelle mission affectée : {lieu_input.upper()}"
                    corps_mail = f"Bonjour,\n\nUne nouvelle mission vous a été attribuée dans le planning.\n\n" \
                                 f"📍 Lieu : {lieu_input.upper()}\n" \
                                 f"📅 Du : {date_debut_sel.strftime('%d/%m/%Y')} au {date_fin_sel.strftime('%d/%m/%Y')}\n" \
                                 f"📝 Statut : {statut_selection}\n\n" \
                                 f"Description :\n{tache_input}"
                    
                    for membre_id in equipe_sel:
                        profil = st.session_state["utilisateurs"].get(membre_id, {})
                        email_dest = profil.get("email_contact", "")
                        if "@" in membre_id:
                            email_dest = membre_id
                            
                        if email_dest and "@" in email_dest:
                            succes = envoyer_email_notification(email_dest, sujet_mail, corps_mail)
                            if succes:
                                compteur_mails += 1
                    
                    st.success("Mission ajoutée et synchronisée avec Google Sheets !")
                    time.sleep(1)
                    st.rerun()

    # ==========================================
    # CÔTÉ ADMIN - ONGLET 3 : RAPPORTS REÇUS
    # ==========================================
    with onglet_actif[2]:
        st.markdown("<h2 style='margin: 0 0 15px 0;'>Rapports Chantiers Reçus</h2>", unsafe_allow_html=True)
        if st.session_state["rapports"]:
            for r in st.session_state["rapports"]:
                with st.expander(f"Rapport de {r.get('employe', 'Inconnu')} — {r.get('date', '')} ({r.get('projet', '')})"):
                    st.write(f"**Lieu/Projet :** {r.get('projet', '')}")
                    st.write(f"**Description du travail :** {r.get('contenu', '')}")
        else:
            st.info("Aucun rapport d'activité n'a été soumis pour le moment.")

    # ==========================================
    # CÔTÉ ADMIN - ONGLET 4 : GESTION DES COMPTES
    # ==========================================
    with onglet_actif[3]:
        st.markdown("<h2 style='margin: 0 0 15px 0;'>Gestion des Comptes Utilisateurs</h2>", unsafe_allow_html=True)
        
        liste_comptes = []
        for identifiant, infos in st.session_state["utilisateurs"].items():
            liste_comptes.append({
                "Nom complet": infos["nom"],
                "Identifiant Principal": identifiant,
                "Email de Notification": infos.get("email_contact", "Non renseigné"),
                "Téléphone": infos.get("tel", "Non renseigné"),
                "Rôle": infos["role"].upper(),
                "Mot de passe": infos["mdp"]
            })
        
        df_comptes = pd.DataFrame(liste_comptes)
        st.dataframe(df_comptes, use_container_width=True, hide_index=True)

# ==========================================
# CÔTÉ EMPLOYÉ - ONGLET 2 : ENVOYER UN RAPPORT
# ==========================================
else:
    with onglet_actif[1]:
        st.markdown("<h2 style='margin: 0 0 15px 0;'>Envoyer un Rapport d'Activité</h2>", unsafe_allow_html=True)
        with st.form("form_rapport_employe", clear_on_submit=True):
            projet_nom = st.text_input("Nom du chantier / Lieu")
            rapport_texte = st.text_area("Détails de l'avancement et remarques")
            
            if st.form_submit_button("Envoyer le rapport", use_container_width=True):
                if projet_nom and rapport_texte:
                    nouveau_rapport = {
                        "employe": user["nom"],
                        "date": datetime.now().strftime("%d/%m/%Y à %H:%M"),
                        "projet": projet_nom.upper(),
                        "contenu": rapport_texte
                    }
                    st.session_state["rapports"].append(nouveau_rapport)
                    
                    # SAUVEGARDE GOOGLE SHEETS
                    sauvegarder_rapport_sheets(nouveau_rapport)
                    st.success("Rapport transmis et enregistré dans Google Sheets !")
