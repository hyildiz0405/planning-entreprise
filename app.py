import streamlit as st
from datetime import datetime, timedelta
import calendar
import extra_streamlit_components as stx
from io import BytesIO
import json
import os

# Importations ReportLab
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

st.set_page_config(page_title="Gestion de Plannings Professionnels", layout="wide")

# --- CONFIGURATION DE LA PERSISTANCE (JSON) ---
FICHIER_DONNEES = "donnees.json"

def charger_donnees():
    """Charge les données depuis le fichier JSON ou initialise les données par défaut."""
    donnees_par_defaut = {
        "utilisateurs": {
            "admin@entreprise.com": {"nom": "Admin", "role": "admin", "mdp": "admin123"},
        },
        "plannings": [
            {
                "id": 1,
                "participants": ["romuald@entreprise.com", "hasan@entreprise.com", "loic@entreprise.com"],
                "date_debut": "2026-06-15", 
                "date_fin": "2026-06-19",
                "lieu": "CAP FERRET",
                "tache": "Chantier – Villa Cap Ferret\nSuivi de la production de la structure principale et raccordements.",
                "statut": "Production"
            },
            {
                "id": 2,
                "participants": ["bob@entreprise.com"],
                "date_debut": "2026-06-17", 
                "date_fin": "2026-06-17",
                "lieu": "BOUTIQUE",
                "tache": "Ouverture de la boutique et gestion des flux de clients matinaux.", 
                "statut": "Planifié"
            }
        ]
    }
    
    if os.path.exists(FICHIER_DONNEES):
        try:
            with open(FICHIER_DONNEES, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return donnees_par_defaut
    else:
        with open(FICHIER_DONNEES, "w", encoding="utf-8") as f:
            json.dump(donnees_par_defaut, f, ensure_ascii=False, indent=4)
        return donnees_par_defaut

def sauvegarder_donnees():
    """Sauvegarde l'état actuel de session_state dans le fichier JSON."""
    donnees_a_sauver = {
        "utilisateurs": st.session_state["utilisateurs"],
        "plannings": st.session_state["plannings"]
    }
    with open(FICHIER_DONNEES, "w", encoding="utf-8") as f:
        json.dump(donnees_a_sauver, f, ensure_ascii=False, indent=4)

# --- CHARGEMENT INITIAL EN SESSION_STATE ---
donnees_chargees = charger_donnees()

if "utilisateurs" not in st.session_state:
    st.session_state["utilisateurs"] = donnees_chargees["utilisateurs"]

if "plannings" not in st.session_state:
    st.session_state["plannings"] = donnees_chargees["plannings"]

if "date_calendrier" not in st.session_state:
    st.session_state["date_calendrier"] = datetime(2026, 6, 15).date()

# Mode édition pour modifier un chantier
if "id_chantier_edition" not in st.session_state:
    st.session_state["id_chantier_edition"] = None

# --- GESTIONNAIRE DE COOKIES ---
cookie_manager = stx.CookieManager()

COULEURS_STATUTS = {
    "Production": {"accent": "#38BDF8", "bg_dot": "#0284C7"},
    "Planifié": {"accent": "#34D399", "bg_dot": "#059669"},
    "Urgent": {"accent": "#F87171", "bg_dot": "#DC2626"}
}

# --- GESTION DE LA SESSION DE MANIÈRE SÉCURISÉE ---
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

# SÉCURITÉ : Écran de connexion
if st.session_state["user_connecte"] is None:
    st.subheader("Connexion")
    email_saisi = st.text_input("Adresse Email")
    mdp_saisi = st.text_input("Mot de passe", type="password")
    
    col_connexion, col_aide = st.columns([1, 1])
    with col_connexion:
        if st.button("Se connecter", use_container_width=True):
            if email_saisi in st.session_state["utilisateurs"] and st.session_state["utilisateurs"][email_saisi]["mdp"] == mdp_saisi:
                st.session_state["user_connecte"] = {**st.session_state["utilisateurs"][email_saisi], "email": email_saisi}
                cookie_manager.set("user_session", email_saisi, max_age=2592000)
                st.rerun()
            else:
                st.error("Identifiants incorrects.")
                
    with col_aide:
        st.markdown("<p style='font-size: 13px; color: #64748B; margin-top: 8px;'>Mot de passe oublié ? Contactez votre administrateur pour récupérer vos accès.</p>", unsafe_allow_html=True)
        
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

# --- GÉNÉRATION DU PDF TABLEAU LINÉAIRE ---
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
        tache_propre = s['tache'].replace('\n', '<br/>')
        
        str_deb = s.get("date_debut", s.get("date", ""))
        str_fin = s.get("date_fin", s.get("date", ""))
        
        d_deb = datetime.strptime(str_deb, "%Y-%m-%d").strftime("%d/%m/%Y") if str_deb else "—"
        d_fin = datetime.strptime(str_fin, "%Y-%m-%d").strftime("%d/%m/%Y") if str_fin else "—"
        
        table_data.append([
            Paragraph(s['lieu'], cell_bold),
            Paragraph(tache_propre, cell_style),
            Paragraph(d_deb, cell_style),
            Paragraph(d_fin, cell_style),
            Paragraph(noms_equipe, cell_style),
            Paragraph(s.get('statut', 'Planifié'), cell_bold)
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

# --- RECUPERATION DU FILTRE ACTUEL ---
employe_filtre = st.session_state.get("emp_filtre_key", "Tous les employés")
user = st.session_state["user_connecte"]
if user["role"] != "admin":
    employe_filtre = user["email"]

# --- COLLECTE DES MISSIONS FILTRÉES ---
missions_semaine = []
for s in st.session_state["plannings"]:
    str_deb = s.get("date_debut", s.get("date"))
    str_fin = s.get("date_fin", s.get("date"))
    if not str_deb or not str_fin:
        continue
    deb_s = datetime.strptime(str_deb, "%Y-%m-%d").date()
    fin_s = datetime.strptime(str_fin, "%Y-%m-%d").date()
    
    if not (fin_s < lundi_semaine or deb_s > dimanche_semaine):
        if employe_filtre != "Tous les employés" and employe_filtre not in s.get("participants", []):
            continue
        missions_semaine.append(s)

# --- BARRE LATÉRALE DE GESTION ---
st.sidebar.markdown(f"### Utilisateur : {user['nom']}")
st.sidebar.markdown(f"**Rôle système :** {user['role'].upper()}")
st.sidebar.markdown("---")

try:
    pdf_data = generer_pdf_global(missions_semaine)
    st.sidebar.download_button(
        label="📄 Télécharger le rapport PDF",
        data=pdf_data,
        file_name=f"planning_{lundi_semaine.strftime('%d_%m_%Y')}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
except Exception:
    st.sidebar.error("Erreur lors de la préparation du PDF.")

st.sidebar.markdown("<br/>", unsafe_allow_html=True)
if st.sidebar.button("Déconnexion", use_container_width=True):
    st.session_state["user_connecte"] = None
    try:
        cookie_manager.delete("user_session")
    except Exception:
        pass
    st.rerun()

# --- CSS PRESTANCE ---
st.markdown("""
    <style>
    .header-jour { text-align: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid #334155; }
    .nom-jour { margin: 0; font-size: 11px; opacity: 0.6; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
    .num-jour { margin: 4px 0 0 0; font-size: 22px; font-weight: 800; }
    
    .zone-shifts-jour { display: flex; flex-direction: column; gap: 12px; }
    
    .shift-card-container { 
        border-radius: 8px; 
        background: #1E293B; 
        border-left: 4px solid #64748B;
        padding: 12px; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 2px;
    }
    
    .shift-top-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
    .shift-lieu { margin: 0; font-size: 11px; font-weight: 700; text-transform: uppercase; color: #94A3B8; }
    .shift-team { margin: 0 0 6px 0; font-size: 11px; color: #38BDF8; font-style: italic; }
    
    .shift-task { 
        margin: 0; 
        font-size: 12px; 
        color: #E2E8F0; 
        white-space: pre-wrap; 
        word-break: break-word;
        line-height: 1.4;
    }
    </style>
""", unsafe_allow_html=True)

# --- SYSTÈME D'ONGLETS ---
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
            return st.session_state["utilisateurs"][x]["nom"]
            
        if user["role"] == "admin":
            st.selectbox("Filtrer par employé", options=liste_employes_choix, format_func=formater_nom_filtre, key="emp_filtre_key")
        else:
            st.session_state["emp_filtre_key"] = user["email"]

    # --- MODE ÉDITION NETTOYÉ ---
    if st.session_state["id_chantier_edition"] is not None:
        chantier_a_editer = next((c for c in st.session_state["plannings"] if c["id"] == st.session_state["id_chantier_edition"]), None)
        if chantier_a_editer:
            st.markdown("<br/>", unsafe_allow_html=True)
            st.info(f"🛠️ Mode édition : Modification du chantier **{chantier_a_editer['lieu']}**")
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
                    if st.form_submit_button("Modifier", use_container_width=True):
                        chantier_a_editer["participants"] = e_equipe
                        chantier_a_editer["date_debut"] = str(e_debut)
                        chantier_a_editer["date_fin"] = str(e_fin)
                        chantier_a_editer["lieu"] = e_lieu.upper()
                        chantier_a_editer["statut"] = e_statut
                        chantier_a_editer["tache"] = e_tache
                        sauvegarder_donnees()
                        st.session_state["id_chantier_edition"] = None
                        st.toast("Chantier mis à jour !")
                        st.rerun()
                with btn_c2:
                    if st.form_submit_button("Annuler", use_container_width=True):
                        st.session_state["id_chantier_edition"] = None
                        st.rerun()

    st.markdown("<br/>", unsafe_allow_html=True)

    # --- AFFICHAGE DU GRILLE-CALENDRIER ---
    cols = st.columns(7)

    for i, jour in enumerate(jours):
        current_date = datetime.strptime(jour["date_str"], "%Y-%m-%d").date()
        with cols[i]:
            st.markdown(f'<div class="header-jour"><p class="nom-jour">{jour["nom"]}</p><p class="num-jour">{jour["date_texte"]}</p></div>', unsafe_allow_html=True)
            st.markdown('<div class="zone-shifts-jour">', unsafe_allow_html=True)
            
            shifts_du_jour = []
            for s in st.session_state["plannings"]:
                str_deb = s.get("date_debut", s.get("date"))
                str_fin = s.get("date_fin", s.get("date"))
                if not str_deb or not str_fin:
                    continue
                deb = datetime.strptime(str_deb, "%Y-%m-%d").date()
                fin = datetime.strptime(str_fin, "%Y-%m-%d").date()
                
                if deb <= current_date <= fin:
                    if employe_filtre != "Tous les employés" and employe_filtre not in s.get("participants", []):
                        continue
                    shifts_du_jour.append(s)
                
            if shifts_du_jour:
                for idx, s in enumerate(shifts_du_jour):
                    statut_style = COULEURS_STATUTS.get(s.get("statut", "Planifié"), {"accent": "#94A3B8", "bg_dot": "#475569"})
                    noms_equipe = ", ".join([st.session_state["utilisateurs"][emp]["nom"] for emp in s.get("participants", []) if emp in st.session_state["utilisateurs"]])
                    
                    if user["role"] == "admin":
                        # Utilisation de chaînes épurées sans aucun mot interdit pour le popover et les clés
                        with st.popover(s['lieu'], use_container_width=True):
                            st.markdown(f"**Chantier :** {s['lieu']}")
                            st.markdown(f"**Équipe :** {noms_equipe}")
                            st.markdown(f"**Tâche :** {s['tache']}")
                            st.markdown(f"**Statut :** {s.get('statut', 'Planifié')}")
                            st.markdown("---")
                            
                            # Clés strictes pour court-circuiter le cache Streamlit
                            if st.button("Modifier", key=f"action-modifier-{s['id']}-{i}-{idx}", use_container_width=True):
                                st.session_state["id_chantier_edition"] = s["id"]
                                st.rerun()
                                
                            if st.button("Supprimer", key=f"action-supprimer-{s['id']}-{i}-{idx}", type="primary", use_container_width=True):
                                st.session_state["plannings"].remove(s)
                                sauvegarder_donnees()
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
                statut_selection = st.selectbox("Statut du chantier", ["Production", "Planifié", "Urgent", "Autre..."])
                statut_autre = st.text_input("Si Autre, écrivez le statut personnalisé ici")
            
            tache_input = st.text_area("Descriptif précis des travaux / tâches à effectuer", placeholder="Détaillez ici l'ordre de mission...", height=150)
            
            st.markdown("<br/>", unsafe_allow_html=True)
            if st.form_submit_button("Planifier", use_container_width=True):
                statut_final = statut_autre.strip() if statut_selection == "Autre..." else statut_selection
                if not statut_final:
                    statut_final = "Planifié"
                
                if equipe_sel and lieu_input and tache_input and (date_fin_sel >= date_debut_sel):
                    nouvel_id = max([s["id"] for s in st.session_state["plannings"]]) + 1 if st.session_state["plannings"] else 1
                    st.session_state["plannings"].append({
                        "id": nouvel_id,
                        "participants": equipe_sel,
                        "date_debut": str(date_debut_sel),
                        "date_fin": str(date_fin_sel),
                        "lieu": lieu_input.upper(),
                        "tache": tache_input,
                        "statut": statut_final
                    })
                    sauvegarder_donnees()
                    st.toast("Mission enregistrée avec succès !")
                    st.rerun()
                elif date_fin_sel < date_debut_sel:
                    st.error("La date de fin ne peut pas être avant la date de début.")
                else:
                    st.error("Veuillez remplir au moins les participants, le lieu et le descriptif.")

# ==========================================
# ONGLET 3 : LISTE DES COMPTES
# ==========================================
if user["role"] == "admin":
    with onglet_actif[2]:
        st.markdown("<h2 style='margin: 0 0 15px 0;'>Créer un nouveau compte employé</h2>", unsafe_allow_html=True)
        
        with st.form("form_centre_compte", clear_on_submit=True):
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                nouvel_email = st.text_input("Adresse e-mail")
                nouveau_nom = st.text_input("Nom")
            with col_c2:
                nouveau_mdp = st.text_input("Mot de passe", type="password")
            
            st.markdown("<br/>", unsafe_allow_html=True)
            if st.form_submit_button("Ajouter l'employé", use_container_width=True):
                if nouvel_email and nouveau_nom and nouveau_mdp:
                    st.session_state["utilisateurs"][nouvel_email] = {"nom": nouveau_nom, "role": "employe", "mdp": nouveau_mdp}
                    sauvegarder_donnees()
                    st.toast(f"Le compte de {nouveau_nom} a été créé !")
                    st.rerun()
                else:
                    st.error("Veuillez remplir tous les champs du formulaire.")

        st.markdown("---")
        st.markdown("<h2 style='margin: 0 0 15px 0;'>Liste des accès et Mots de Passe</h2>", unsafe_allow_html=True)
        
        donnees_comptes = []
        for mail, data in st.session_state["utilisateurs"].items():
            donnees_comptes.append({
                "Nom complet": data["nom"],
                "Adresse Email": mail,
                "Mot de Passe": data["mdp"],
                "Rôle": data["role"].upper()
            })
        
        st.dataframe(donnees_comptes, use_container_width=True, hide_index=True)