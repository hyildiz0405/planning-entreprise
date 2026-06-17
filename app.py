import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import extra_streamlit_components as stx
from io import BytesIO

# Importations ReportLab pour le PDF
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURATION ---
st.set_page_config(page_title="Planning Arhen Energy", page_icon="logo.png", layout="wide")

# URL de ton Google Sheets (Lecture seule via CSV pour la rapidité)
SHEET_ID = "1nIiT1ql3mL4VmcBuLlST8QD0QKItAHq72B9P0THH-ns"
URL_USERS = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=utilisateurs"
URL_PLANS = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=plannings"

def charger_donnees():
    """Charge les utilisateurs et chantiers depuis Google Sheets."""
    try:
        df_u = pd.read_csv(URL_USERS)
        df_u.columns = [c.lower().strip() for c in df_u.columns]
        utilisateurs = {}
        for _, r in df_u.iterrows():
            mail = str(r['email']).strip()
            utilisateurs[mail] = {"nom": str(r['nom']), "role": str(r['role']).lower(), "mdp": str(r['mdp'])}
    except:
        utilisateurs = {"admin@arhen.energy": {"nom": "Admin", "role": "admin", "mdp": "admin123"}}

    try:
        df_p = pd.read_csv(URL_PLANS)
        df_p.columns = [c.lower().strip() for c in df_p.columns]
        plannings = []
        for _, r in df_p.iterrows():
            parts = [p.strip() for p in str(r['participants']).split(",") if p.strip()]
            plannings.append({
                "id": int(r['id']), "participants": parts, 
                "date_debut": str(r['date_debut']), "date_fin": str(r['date_fin']),
                "lieu": str(r['lieu']).upper(), "tache": str(r['tache']), "statut": str(r['statut'])
            })
    except:
        plannings = []
    return utilisateurs, plannings

# Initialisation Session State
if "utilisateurs" not in st.session_state:
    u, p = charger_donnees()
    st.session_state["utilisateurs"] = u
    st.session_state["plannings"] = p

if "date_calendrier" not in st.session_state:
    st.session_state["date_calendrier"] = datetime.now().date()

# --- GESTIONNAIRE DE COOKIES (CONNEXION PERSISTANTE) ---
cookie_manager = stx.CookieManager()

# --- LOGIQUE DE CONNEXION ---
if "user_connecte" not in st.session_state:
    saved_user = cookie_manager.get(cookie="user_session")
    if saved_user in st.session_state["utilisateurs"]:
        st.session_state["user_connecte"] = {**st.session_state["utilisateurs"][saved_user], "email": saved_user}
    else:
        st.session_state["user_connecte"] = None

if st.session_state["user_connecte"] is None:
    st.title("Connexion")
    e_mail = st.text_input("Email").strip()
    m_dp = st.text_input("Mot de passe", type="password").strip()
    if st.button("Se connecter", use_container_width=True):
        if e_mail in st.session_state["utilisateurs"] and st.session_state["utilisateurs"][e_mail]["mdp"] == m_dp:
            st.session_state["user_connecte"] = {**st.session_state["utilisateurs"][e_mail], "email": e_mail}
            cookie_manager.set("user_session", e_mail, max_age=2592000)
            st.rerun()
        else:
            st.error("Identifiants incorrects")
    st.stop()

# --- ACCÈS RÉUSSI ---
user = st.session_state["user_connecte"]

# --- CALCUL DES DATES SEMAINE ---
date_sel = st.session_state["date_calendrier"]
lundi = date_sel - timedelta(days=date_sel.weekday())
jours = []
for i in range(7):
    d = lundi + timedelta(days=i)
    jours.append({"nom": ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"][i], "date": d})

# --- FONCTION PDF ---
def generer_pdf(missions):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph(f"Planning Arhen Energy - Semaine du {lundi.strftime('%d/%m/%Y')}", styles['Title']))
    
    data = [["Lieu", "Mission", "Début", "Fin", "Équipe", "Statut"]]
    for m in missions:
        equipe = ", ".join([st.session_state['utilisateurs'].get(e, {'nom': e})['nom'] for e in m['participants']])
        data.append([m['lieu'], m['tache'][:50], m['date_debut'], m['date_fin'], equipe, m['statut']])
    
    t = Table(data, colWidths=[100, 250, 70, 70, 150, 80])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.black), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- BARRE LATÉRALE ---
st.sidebar.title(f"Salut, {user['nom']}")
st.sidebar.info(f"Rôle : {user['role'].upper()}")

# Bouton PDF
missions_visibles = [m for m in st.session_state["plannings"] if not (datetime.strptime(m["date_fin"], "%Y-%m-%d").date() < lundi or datetime.strptime(m["date_debut"], "%Y-%m-%d").date() > lundi + timedelta(days=6))]
if missions_visibles:
    st.sidebar.download_button("📄 Télécharger le PDF", data=generer_pdf(missions_visibles), file_name="planning.pdf", mime="application/pdf", use_container_width=True)

if st.sidebar.button("Déconnexion", use_container_width=True):
    st.session_state["user_connecte"] = None
    cookie_manager.delete("user_session")
    st.rerun()

if st.sidebar.button("🔄 Forcer l'actualisation Google Sheets", use_container_width=True):
    u, p = charger_donnees()
    st.session_state["utilisateurs"] = u
    st.session_state["plannings"] = p
    st.rerun()

# --- INTERFACE ---
if user["role"] == "admin":
    tabs = st.tabs(["📅 Calendrier", "➕ Planifier", "👥 Gestion des Comptes"])
else:
    tabs = st.tabs(["📅 Calendrier"])

# TAB 1 : CALENDRIER
with tabs[0]:
    st.date_input("Aller à une date", key="date_calendrier")
    cols = st.columns(7)
    for i, j in enumerate(jours):
        with cols[i]:
            st.markdown(f"**{j['nom']} {j['date'].strftime('%d/%m')}**")
            for p in st.session_state["plannings"]:
                d_deb = datetime.strptime(p["date_debut"], "%Y-%m-%d").date()
                d_fin = datetime.strptime(p["date_fin"], "%Y-%m-%d").date()
                if d_deb <= j["date"] <= d_fin:
                    with st.expander(f"{p['lieu']}"):
                        st.caption(f"Status: {p['statut']}")
                        st.write(p["tache"])
                        if user["role"] == "admin":
                            if st.button("Supprimer", key=f"del-{p['id']}-{i}"):
                                st.session_state["plannings"].remove(p)
                                st.rerun()

# TAB 2 : PLANIFIER
if user["role"] == "admin":
    with tabs[1]:
        with st.form("new_plan"):
            lieu = st.text_input("Lieu")
            tache = st.text_area("Description")
            equipe = st.multiselect("Équipe", options=list(st.session_state["utilisateurs"].keys()), format_func=lambda x: st.session_state["utilisateurs"][x]["nom"])
            d1 = st.date_input("Début")
            d2 = st.date_input("Fin")
            stat = st.selectbox("Statut", ["Production", "Planifié", "Urgent"])
            if st.form_submit_button("Ajouter à l'écran"):
                nid = max([x["id"] for x in st.session_state["plannings"]] + [0]) + 1
                st.session_state["plannings"].append({"id": nid, "lieu": lieu.upper(), "tache": tache, "participants": equipe, "date_debut": str(d1), "date_fin": str(d2), "statut": stat})
                st.success("Ajouté ! Note : n'oubliez pas de copier vos données vers Google Sheets pour les fixer.")
                st.rerun()

# TAB 3 : GESTION DES COMPTES (FONCTIONNALITÉS RESTAURÉES)
if user["role"] == "admin":
    with tabs[2]:
        st.subheader("Créer un compte")
        with st.form("new_user"):
            c1, c2 = st.columns(2)
            n_mail = c1.text_input("Email")
            n_nom = c2.text_input("Nom complet")
            n_mdp = c1.text_input("Mot de passe")
            n_role = c2.selectbox("Rôle", ["admin", "employe"])
            if st.form_submit_button("Créer le compte"):
                st.session_state["utilisateurs"][n_mail] = {"nom": n_nom, "mdp": n_mdp, "role": n_role}
                st.success("Compte ajouté !")
                st.rerun()

        st.divider()
        st.subheader("Liste des comptes existants")
        for mail, info in list(st.session_state["utilisateurs"].items()):
            with st.expander(f"👤 {info['nom']} ({mail}) - {info['role'].upper()}"):
                # Changer le MDP
                nouveau_mdp = st.text_input(f"Nouveau MDP pour {info['nom']}", value=info["mdp"], key=f"pwd-{mail}")
                if nouveau_mdp != info["mdp"]:
                    if st.button("Enregistrer le MDP", key=f"save-{mail}"):
                        st.session_state["utilisateurs"][mail]["mdp"] = nouveau_mdp
                        st.success("Mot de passe changé !")
                        st.rerun()
                
                # Supprimer le compte
                if mail != user["email"]:
                    if st.button("🗑️ Supprimer ce compte", key=f"del-user-{mail}"):
                        del st.session_state["utilisateurs"][mail]
                        st.warning("Compte supprimé !")
                        st.rerun()

        # Bloc de sauvegarde pour l'admin
        st.divider()
        st.subheader("💾 Sauvegarde vers Google Sheets")
        st.write("Copiez ces tableaux dans votre Google Sheets pour enregistrer définitivement.")
        col_u, col_p = st.columns(2)
        with col_u:
            st.write("**Onglet utilisateurs :**")
            df_u_save = pd.DataFrame([{"email": k, "nom": v["nom"], "role": v["role"], "mdp": v["mdp"]} for k, v in st.session_state["utilisateurs"].items()])
            st.dataframe(df_u_save, hide_index=True)
        with col_p:
            st.write("**Onglet plannings :**")
            df_p_save = pd.DataFrame(st.session_state["plannings"])
            # Formater les participants en texte pour le Sheets
            if not df_p_save.empty:
                df_p_save["participants"] = df_p_save["participants"].apply(lambda x: ",".join(x))
            st.dataframe(df_p_save, hide_index=True)
