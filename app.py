import streamlit as st
from datetime import datetime, timedelta
import calendar
import extra_streamlit_components as stx
from io import BytesIO, StringIO
import json
import os
import pandas as pd
import requests

# Importations ReportLab
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURATION INITIALE DE L'APPLICATION ---
st.set_page_config(page_title="Planning Entreprise", page_icon="logo.png", layout="wide")

# --- CONFIGURATION DE LA BASE DE DONNÉES GOOGLE SHEETS ---
# Ton lien Google Sheets converti pour l'export CSV en direct par onglet
URL_BASE_SHEET = "https://docs.google.com/spreadsheets/d/1nIiT1ql3mL4VmcBuLlST8QD0QKItAHq72B9P0THH-ns/gviz/tq?tqx=out:csv"

def charger_donnees_sheets():
    """Charge les utilisateurs et plannings depuis le Google Sheets."""
    # Chargement des utilisateurs
    try:
        url_users = f"{URL_BASE_SHEET}&sheet=utilisateurs"
        df_users = pd.read_csv(url_users)
        # Nettoyage des colonnes au cas où
        df_users.columns = [c.lower().strip() for c in df_users.columns]
        utilisateurs = {}
        for _, row in df_users.iterrows():
            email = str(row['email']).strip()
            utilisateurs[email] = {
                "nom": str(row['nom']).strip(),
                "role": str(row['role']).strip().lower(),
                "mdp": str(row['mdp']).strip()
            }
    except Exception:
        # En cas de problème de lecture (ex: tableau vide), compte par défaut
        utilisateurs = {"admin@entreprise.com": {"nom": "Admin", "role": "admin", "mdp": "admin123"}}

    # Chargement des plannings
    try:
        url_plannings = f"{URL_BASE_SHEET}&sheet=plannings"
        df_plan = pd.read_csv(url_plannings)
        df_plan.columns = [c.lower().strip() for c in df_plan.columns]
        plannings = []
        for _, row in df_plan.iterrows():
            # Conversion de la chaîne des participants en liste
            parts = str(row['participants']).split(",")
            parts = [p.strip() for p in parts if p.strip()]
            
            plannings.append({
                "id": int(row['id']),
                "participants": parts,
                "date_debut": str(row['date_debut']).strip(),
                "date_fin": str(row['date_fin']).strip(),
                "lieu": str(row['lieu']).strip().upper(),
                "tache": str(row['tache']).strip(),
                "statut": str(row['statut']).strip()
            })
    except Exception:
        plannings = []

    return utilisateurs, plannings

# --- CHARGEMENT INITIAL (Pour éviter de saturer le Sheets, on charge une fois par rafraîchissement) ---
if "utilisateurs" not in st.session_state or st.sidebar.button("🔄 Actualiser les données Google Sheets", use_container_width=True):
    utils, plans = charger_donnees_sheets()
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
    
    col_connexion, col_aide = st.columns([1, 1])
    with col_connexion:
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

# --- FILTRES ---
employe_filtre = st.session_state.get("emp_filtre_key", "Tous les employés")
if user["role"] != "admin":
    employe_filtre = user["email"]

missions_semaine = []
for s in st.session_state["plannings"]:
    str_deb = s.get("date_debut")
    str_fin = s.get("date_fin")
    if not str_deb or not str_fin or str_deb == "nan" or str_fin == "nan":
        continue
    try:
        deb_s = datetime.strptime(str_deb, "%Y-%m-%d").date()
        fin_s = datetime.strptime(str_fin, "%Y-%m-%d").date()
        if not (fin_s < lundi_semaine or deb_s > dimanche_semaine):
            if employe_filtre != "Tous les employés" and employe_filtre not in s.get("participants", []):
                continue
            missions_semaine.append(s)
    except Exception:
        continue

# --- BARRE LATÉRALE ---
st.sidebar.markdown(f"### Utilisateur : {user['nom']}")
st.sidebar.markdown(f"**Rôle :** {user['role'].upper()}")
st.sidebar.markdown("---")

# Instructions pour la sauvegarde
if user["role"] == "admin":
    st.sidebar.info("💡 **Sauvegarde :** Les modifications en direct sur le téléphone sont temporaires. Pour fixer vos modifications ou nouveaux comptes définitivement, copiez le tableau ci-dessous et collez-le dans votre Google Sheets.")

    # Boutons d'export rapides pour l'admin
    with st.sidebar.expander("📥 Étape de Sauvegarde Rapide"):
        # Export Utilisateurs
        df_u_save = pd.DataFrame([{"email": k, "nom": v["nom"], "role": v["role"], "mdp": v["mdp"]} for k, v in st.session_state["utilisateurs"].items()])
        st.markdown("**1. Onglet Utilisateurs :**")
        st.dataframe(df_u_save, hide_index=True)
        
        # Export Plannings
        export_p = []
        for p in st.session_state["plannings"]:
            export_p.append({
                "id": p["id"],
                "participants": ",".join(p["participants"]),
                "date_debut": p["date_debut"],
                "date_fin": p["date_fin"],
                "lieu": p["lieu"],
                "tache": p["tache"],
                "statut": p["statut"]
            })
        df_p_save = pd.DataFrame(export_p)
        st.markdown("**2. Onglet Plannings :**")
        st.dataframe(df_p_save, hide_index=True)

if st.sidebar.button("Déconnexion", use_container_width=True):
    st.session_state["user_connecte"] = None
    try: cookie_manager.delete("user_session")
    except Exception: pass
    st.rerun()

# --- STYLE CSS ---
st.markdown("""
    <style>
    .header-jour { text-align: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid #334155; }
    .nom-jour { margin: 0; font-size: 11px; opacity: 0.6; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
    .num-jour { margin: 4px 0 0 0; font-size: 22px; font-weight: 800; }
    .zone-shifts-jour { display: flex; flex-direction: column; gap: 12px; }
    .shift-card-container { border-radius: 8px; background: #1E293B; border-left: 4px solid #64748B; padding: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); margin-bottom: 2px; }
    .shift-top-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
    .shift-lieu { margin: 0; font-size: 11px; font-weight: 700; text-transform: uppercase; color: #94A3B8; }
    .shift-team { margin: 0 0 6px 0; font-size: 11px; color: #38BDF8; font-style: italic; }
    .shift-task { margin: 0; font-size: 12px; color: #E2E8F0; white-space: pre-wrap; word-break: break-word; line-height: 1.4; }
    </style>
""", unsafe_allow_html=True)

# --- ONGLETS ---
if user["role"] == "admin":
    onglet_actif = st.tabs(["Calendrier", "Planifier", "Liste des Comptes"])
else:
    onglet_actif = st.tabs(["Calendrier"])

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
            return st.session_state["utilisateurs"].get(x, {}).get("nom", x)
            
        if user["role"] == "admin":
            st.selectbox("Filtrer par employé", options=liste_employes_choix, format_func=formater_nom_filtre, key="emp_filtre_key")
        else:
            st.session_state["emp_filtre_key"] = user["email"]

    # Mode Édition
    if st.session_state["id_chantier_edition"] is not None:
        chantier_a_editer = next((c for c in st.session_state["plannings"] if c["id"] == st.session_state["id_chantier_edition"]), None)
        if chantier_a_editer:
            st.info(f"🛠️ Mode édition : Modification de {chantier_a_editer['lieu']}")
            with st.form("form_edition_chantier"):
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    e_equipe = st.multiselect("Équipe", options=list(st.session_state["utilisateurs"].keys()), default=chantier_a_editer["participants"], format_func=lambda x: st.session_state["utilisateurs"][x]["nom"])
                    e_debut = st.date_input("Début", datetime.strptime(chantier_a_editer["date_debut"], "%Y-%m-%d").date(), format="DD/MM/YYYY")
                    e_fin = st.date_input("Fin", datetime.strptime(chantier_a_editer["date_fin"], "%Y-%m-%d").date(), format="DD/MM/YYYY")
                with col_e2:
                    e_lieu = st.text_input("Lieu", chantier_a_editer["lieu"])
                    e_statut = st.selectbox("Statut", ["Production", "Planifié", "Urgent"], index=["Production", "Planifié", "Urgent"].index(chantier_a_editer["statut"]) if chantier_a_editer["statut"] in ["Production", "Planifié", "Urgent"] else 1)
                e_tache = st.text_area("Descriptif", chantier_a_editer["tache"])
                
                btn_c1, btn_c2 = st.columns(2)
                with btn_c1:
                    if st.form_submit_button("Modifier à l'écran", use_container_width=True):
                        chantier_a_editer["participants"] = e_equipe
                        chantier_a_editer["date_debut"] = str(e_debut)
                        chantier_a_editer["date_fin"] = str(e_fin)
                        chantier_a_editer["lieu"] = e_lieu.upper()
                        chantier_a_editer["statut"] = e_statut
                        chantier_a_editer["tache"] = e_tache
                        st.session_state["id_chantier_edition"] = None
                        st.success("Modifié à l'écran ! Pensez à actualiser votre Google Sheets avec le tableau de gauche si vous voulez verrouiller.")
                        st.rerun()
                with btn_c2:
                    if st.form_submit_button("Annuler"):
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
                str_deb = s.get("date_debut")
                str_fin = s.get("date_fin")
                if not str_deb or not str_fin or str_deb == "nan" or str_fin == "nan": continue
                try:
                    deb = datetime.strptime(str_deb, "%Y-%m-%d").date()
                    fin = datetime.strptime(str_fin, "%Y-%m-%d").date()
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
                            st.markdown(f"**Chantier :** {s['lieu']}")
                            st.markdown(f"**Équipe :** {noms_equipe}")
                            st.markdown(f"**Tâche :** {s['tache']}")
                            st.markdown("---")
                            if st.button("Modifier", key=f"ed-{s['id']}-{i}-{idx}", use_container_width=True):
                                st.session_state["id_chantier_edition"] = s["id"]
                                st.rerun()
                            if st.button("Supprimer", key=f"del-{s['id']}-{i}-{idx}", type="primary", use_container_width=True):
                                st.session_state["plannings"].remove(s)
                                st.rerun()
                    else:
                        st.markdown(f"""
                        <div class="shift-card-container" style="border-left-color: {statut_style['accent']};">
                            <div class="shift-top-row">
                                <span class="status-dot" style="background-color: {statut_style['bg_dot']};"></span>
                                <p class="shift-lieu">{s['lieu']}</p>
                            </div>
                            <p class="shift-team">Equipe: {noms_equipe}</p>
                            <p class="shift-task">{s['tache']}</p>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.markdown("<p style='text-align: center; opacity: 0.2; font-size: 12px; margin-top: 10px;'>Aucun chantier</p>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# ONGLET 2 : PLANIFIER
# ==========================================
if user["role"] == "admin":
    with onglet_actif[1]:
        st.markdown("<h2 style='margin: 0 0 15px 0;'>Planifier une Mission</h2>", unsafe_allow_html=True)
        with st.form("form_centre_shift", clear_on_submit=True):
            col_1, col_2 = st.columns(2)
            with col_1:
                equipe_sel = st.multiselect("Équipe / Participants requis", options=list(st.session_state["utilisateurs"].keys()), format_func=lambda x: st.session_state["utilisateurs"][x]["nom"])
                date_debut_sel = st.date_input("Date de DÉBUT", datetime.now().date(), format="DD/MM/YYYY")
                date_fin_sel = st.date_input("Date de FIN", datetime.now().date(), format="DD/MM/YYYY")
            with col_2:
                lieu_input = st.text_input("Lieu ou Nom du projet")
                statut_selection = st.selectbox("Statut du chantier", ["Production", "Planifié", "Urgent"])
            
            tache_input = st.text_area("Descriptif précis des travaux", placeholder="Détaillez ici l'ordre de mission...")
            
            if st.form_submit_button("Ajouter au planning à l'écran", use_container_width=True):
                if equipe_sel and lieu_input and tache_input and (date_fin_sel >= date_debut_sel):
                    nouvel_id = max([s["id"] for s in st.session_state["plannings"]]) + 1 if st.session_state["plannings"] else 1
                    st.session_state["plannings"].append({
                        "id": nouvel_id,
                        "participants": equipe_sel,
                        "date_debut": str(date_debut_sel),
                        "date_fin": str(date_fin_sel),
                        "lieu": lieu_input.upper(),
                        "tache": tache_input,
                        "statut": statut_selection
                    })
                    st.success("Mission ajoutée à l'écran ! Utilisez le volet de gauche pour la sauvegarder définitivement sur Google Sheets.")
                    st.rerun()

# ==========================================
# ONGLET 3 : LISTE DES COMPTES
# ==========================================
if user["role"] == "admin":
    with onglet_actif[2]:
        st.markdown("<h2 style='margin: 0 0 15px 0;'>Créer un nouveau compte</h2>", unsafe_allow_html=True)
        with st.form("form_centre_compte", clear_on_submit=True):
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                nouvel_email = st.text_input("Adresse e-mail").strip()
                nouveau_nom = st.text_input("Nom")
            with col_c2:
                nouveau_mdp = st.text_input("Mot de passe", type="password")
                nouveau_role = st.selectbox("Rôle du compte", options=["Admin", "Employé"])
            
            if st.form_submit_button("Ajouter le compte à l'écran", use_container_width=True):
                if nouvel_email and nouveau_nom and nouveau_mdp:
                    st.session_state["utilisateurs"][nouvel_email] = {
                        "nom": nouveau_nom, 
                        "role": "admin" if nouveau_role == "Admin" else "employe", 
                        "mdp": nouveau_mdp
                    }
                    st.success(f"Compte créé à l'écran ! Enregistrez via le volet de gauche sur votre Google Sheets.")
                    st.rerun()

        st.markdown("---")
        st.markdown("<h2 style='margin: 0 0 15px 0;'>Gestion des accès</h2>", unsafe_allow_html=True)
        for mail, data in list(st.session_state["utilisateurs"].items()):
            with st.expander(f"👤 {data['nom']} ({mail}) — {data['role'].upper()}"):
                nouveau_mdp_saisi = st.text_input("Modifier le mot de passe", value=data["mdp"], key=f"mdp-{mail}", type="password")
                if nouveau_mdp_saisi != data["mdp"]:
                    if st.button("Enregistrer le MDP à l'écran", key=f"btn-mdp-{mail}"):
                        st.session_state["utilisateurs"][mail]["mdp"] = nouveau_mdp_saisi
                        st.rerun()
                if mail != user["email"]:
                    if st.button("❌ Supprimer le compte de l'écran", key=f"btn-suppr-{mail}", type="primary"):
                        del st.session_state["utilisateurs"][mail]
                        st.rerun()
