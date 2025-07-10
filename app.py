import csv
import json
import hashlib
from pathlib import Path
from datetime import datetime
import streamlit as st
import os
from PIL import Image
import pandas as pd
import plotly.express as px
import base64

# 👉 Forcer le mode large
st.set_page_config(layout="wide")

def get_profile_picture(username):
    # Chemin par défaut
    default_path = "automatic.png"
    
    # Vérifier si l'utilisateur a une photo personnalisée
    custom_path = f"users/acuitis langon/{username}.png"
    if os.path.exists(custom_path):
        return custom_path
    else:
        return default_path

# -- Barre d'état en haut de page --
def status_bar():
    # Créer une ligne de colonnes pour la disposition
    col1, col2, col3 = st.columns([1,1,1])
    
    # Afficher le logo pingster en haut à droite
    with col3:
        pingster_logo = Image.open("pingster.png")
        st.image(pingster_logo, width=1020)
    
    # Afficher les infos utilisateur
    if "username" in st.session_state and st.session_state.username:
        profile_pic = get_profile_picture(st.session_state.username)
        with col1:
            st.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-top: 10px; display: flex; align-items: center; gap: 15px;">
                <img src="data:image/png;base64,{base64.b64encode(open(profile_pic, "rb").read()).decode()}" 
                     style="width: 70px; height: 70px; border-radius: 50%; object-fit: cover;">
                <div style="display: flex; flex-direction: column; gap: 5px;">
                    <p style="margin: 0; font-weight: bold; font-size: 14px;">Connecté en tant que</p>
                    <p style="margin: 0; color: #5872fb; font-size: 18px; font-weight: 500;">{st.session_state.username}</p>
                    <p style="margin: 0; font-size: 14px; color: #555;">{users[st.session_state.username]['magasin']}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # Afficher le dernier fichier chargé uniquement pour l'onglet Facture
    if st.session_state.get("current_tab") == "Relance Facture" and uploads:
        last_upload = uploads[-1]
        dt_str = last_upload.get("datetime", "")
        if " à " in dt_str:
            date_part, time_part = dt_str.split(" à ")
            dt_obj = datetime.strptime(date_part + time_part, "%Y%m%d%H%M%S")
            formatted_date = dt_obj.strftime("%d/%m/%Y à %H:%M")
        else:
            formatted_date = dt_str
        
        last_upload_user = last_upload.get("user", "N/A")
        
        with col2:
            st.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-top: 10px;">
                <p style="margin: 0; font-weight: bold; font-size: 14px;">Dernier fichier chargé par</p>
                <p style="margin: 0; color: #5872fb; font-size: 16px; font-weight: 500;">{last_upload_user}</p>
                <p style="margin: 0; font-size: 14px; color: #555;">{formatted_date}</p>
            </div>
            """, unsafe_allow_html=True)

# Afficher le logo principal en sidebar (en haut à gauche)
logo = Image.open("logo.png")
st.sidebar.image(logo, width=620)

# -- Gestion utilisateurs avec mot de passe hashé --
USERS_FILE = "users.json"

def load_users():
    if Path(USERS_FILE).exists():
        try:
            with open(USERS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()

users = load_users()

st.sidebar.markdown("<h1 style='color: #5872fb;'>Connexion</h1>", unsafe_allow_html=True)
st.sidebar.info("Pour toute demande d'identifiant, merci de contacter le support à l'adresse support@maje-solutions.com.")

if "username" not in st.session_state:
    st.session_state.username = None

if st.session_state.username is None:
    username_input = st.sidebar.text_input("Nom d'utilisateur")
    password_input = st.sidebar.text_input("Mot de passe", type="password")
    if st.sidebar.button("Se connecter"):
        username_input = username_input.strip()
        if not username_input:
            st.sidebar.error("Merci d'entrer un nom d'utilisateur.")
        elif username_input.lower() not in [k.lower() for k in users.keys()]:
            st.sidebar.error("Utilisateur inconnu.")
        else:
            exact_username = next(k for k in users.keys() if k.lower() == username_input.lower())
            if hash_password(password_input) == users[exact_username]["password_hash"]:
                st.session_state.username = exact_username
                st.rerun()
            else:
                st.sidebar.error("Mot de passe incorrect.")
else:
    if st.sidebar.button("Se déconnecter"):
        st.session_state.clear()  # Reset complet de la session
        st.rerun()

if st.session_state.username is None:
    st.stop()

USER = st.session_state.username
if USER not in users:
    st.error(f"Utilisateur {USER} introuvable dans la base.")
    st.stop()

if "magasin" not in users[USER]:
    st.error(f"Utilisateur {USER} n'a pas de magasin défini dans users.json.")
    st.stop()

MAGASIN = users[USER]["magasin"].lower()

# -- Dossier commun au groupe (magasin) --
GROUP_FOLDER = Path("users") / MAGASIN
GROUP_FOLDER.mkdir(parents=True, exist_ok=True)

# -- Gestion des relances partagées au niveau de la magasin --
fichier_relances = GROUP_FOLDER / "relances.json"
relances = {}
if fichier_relances.exists():
    try:
        with open(fichier_relances, encoding="utf-8") as f:
            contenu = f.read().strip()
            if contenu:
                raw = json.loads(contenu)
                for facture, data in raw.items():
                    if isinstance(data, list):
                        relances[facture] = data
                    elif isinstance(data, dict):
                        relances[facture] = [data]
                    else:
                        relances[facture] = []
    except json.JSONDecodeError:
        st.warning("⚠️ Fichier relances.json invalide, il sera écrasé à la prochaine sauvegarde.")

# -- Gestion historique uploads partagés (magasin) --
uploads_file = GROUP_FOLDER / "uploads.json"
uploads = []
if uploads_file.exists():
    try:
        with open(uploads_file, encoding="utf-8") as f:
            uploads = json.load(f)
    except:
        uploads = []

# -- Gestion des devis --
devis_file = GROUP_FOLDER / "devis.json"
devis = []
if devis_file.exists():
    try:
        with open(devis_file, encoding="utf-8") as f:
            devis = json.load(f)
    except:
        devis = []

# -- Style personnalisé pour les onglets --
st.markdown("""
<style>
    /* Style pour les onglets */
    .stRadio > div {
        flex-direction: row !important;
        gap: 10px;
    }
    
    .stRadio > div > label {
        background-color: #f0f2f6 !important;
        padding: 10px 20px !important;
        border-radius: 20px !important;
        margin: 0 !important;
        transition: all 0.3s ease;
    }
    
    .stRadio > div > label:hover {
        background-color: #e0e2e6 !important;
    }
    
    .stRadio > div > label[data-baseweb="radio"] > div:first-child {
        background-color: #5872fb !important;
    }
    
    .stRadio > div > label[data-baseweb="radio"] > div:nth-child(2) {
        color: #5872fb !important;
        font-weight: 500 !important;
    }
    
    /* Espace sous la barre de statut */
    .stApp > div:first-child {
        margin-bottom: 30px !important;
    }
</style>
""", unsafe_allow_html=True)

# -- Onglets principaux --
st.session_state.current_tab = st.sidebar.radio(
    "Navigation",
    ["Relance Facture", "Relance Devis"],
    index=0,
    label_visibility="collapsed"
)

# Afficher la barre d'état
status_bar()

# Ajout d'espace entre la barre d'état et le contenu
st.markdown("<div style='margin-bottom: 30px;'></div>", unsafe_allow_html=True)

# --- Onglet Relance Facture ---
if st.session_state.current_tab == "Relance Facture":
    # --- Sélection du fichier uploadé à afficher ---
    if uploads:
        st.sidebar.markdown("<h3 style='color: #5872fb;'>Sélection de la liste à afficher</h3>", unsafe_allow_html=True)
        # Créer des noms simplifiés pour l'affichage
        display_names = [f"Liste {i+1}" for i in range(len(uploads))]
        # Garder une correspondance avec les noms réels
        filename_mapping = {f"Liste {i+1}": up["filename"] for i, up in enumerate(uploads)}
        
        selected_display = st.sidebar.selectbox(
            "Choisis une liste uploadée",
            options=display_names,
            index=len(display_names)-1,
            format_func=lambda x: x  # Affiche juste "Liste X"
        )
        selected_filename = filename_mapping[selected_display]
    else:
        selected_filename = None

    # -- Upload du fichier CSV --
    uploaded_file = st.file_uploader("📤 Déposer un nouveau CSV Cosium", type="csv")

    def lire_csv_depuis_fichier(file_path):
        try:
            with open(file_path, encoding="ISO-8859-1") as f:
                toutes_lignes = []
                for line in f:
                    line = line.strip()
                    if "total" in line.lower():
                        break
                    toutes_lignes.append(line)
            idx_entete = next((i for i, l in enumerate(toutes_lignes) if "facture" in l.lower()), None)
            if idx_entete is None:
                st.error("❌ En-tête introuvable dans le CSV.")
                return None
            lignes_utiles = toutes_lignes[idx_entete:]
            reader = list(csv.DictReader(lignes_utiles, delimiter=";"))
            return reader
        except Exception as e:
            st.error(f"Erreur lecture fichier CSV : {e}")
            return None

    def comparer_factures(reader_old, reader_new):
        def extract_facture_data(reader):
            factures = {}
            for row in reader:
                type_brut = row.get("Type", "").strip()
                if type_brut == "CHQ-DIFF":
                    continue
                    
                numero_facture = None
                for key in row.keys():
                    if "facture" in key.lower():
                        numero_facture = row.get(key)
                        break
                if numero_facture:
                    numero_facture = numero_facture.strip()
                    client = row.get("Client", "").strip()
                    factures[numero_facture] = client
            return factures

        old_data = extract_facture_data(reader_old) if reader_old else {}
        new_data = extract_facture_data(reader_new) if reader_new else {}

        old_nums = set(old_data.keys())
        new_nums = set(new_data.keys())

        nouvelles_factures = new_nums - old_nums
        factures_supprimees = old_nums - new_nums
        factures_payees = factures_supprimees

        return {
            "nouvelles": len(nouvelles_factures),
            "payees": len(factures_payees),
            "liste_nouvelles": [(nf, new_data[nf]) for nf in sorted(nouvelles_factures)],
            "liste_payees": [(pf, old_data[pf]) for pf in sorted(factures_supprimees)]
        }

    if uploaded_file and "last_uploaded_name" not in st.session_state:
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{now_str}_{uploaded_file.name}"
        file_path = GROUP_FOLDER / filename
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        st.success(f"Fichier sauvegardé : {filename}")

        # Ajouter le numéro de liste
        list_number = len(uploads) + 1
        
        uploads.append({
            "filename": filename, 
            "datetime": now_str.replace("_", " à "),
            "user": USER,
            "list_number": list_number
        })
        with open(uploads_file, "w", encoding="utf-8") as f:
            json.dump(uploads, f, ensure_ascii=False, indent=2)

        st.session_state["last_uploaded_name"] = filename  # Marque comme déjà uploadé

        if len(uploads) > 1:
            previous_file_path = GROUP_FOLDER / uploads[-2]["filename"]
            reader_old = lire_csv_depuis_fichier(previous_file_path)
            reader_new = lire_csv_depuis_fichier(file_path)

            if reader_old is not None and reader_new is not None:
                diffs = comparer_factures(reader_old, reader_new)

                st.info(f"📊 Différences avec la liste précédente : +{diffs['nouvelles']} nouvelles factures, {diffs['payees']} factures payées")

                if diffs["liste_nouvelles"]:
                    with st.expander("🆕 Voir les nouvelles factures"):
                        for nf, client in diffs["liste_nouvelles"]:
                            st.markdown(f"- **{nf}** — {client}")

                if diffs["liste_payees"]:
                    with st.expander("✅ Voir les factures payées"):
                        for pf, client in diffs["liste_payees"]:
                            st.markdown(f"- ~~{pf}~~ — {client}")

        selected_filename = filename
    elif "last_uploaded_name" in st.session_state:
        selected_filename = st.session_state["last_uploaded_name"]

    # --- Chargement du fichier CSV sélectionné ---
    if selected_filename:
        csv_path = GROUP_FOLDER / selected_filename
        reader = lire_csv_depuis_fichier(csv_path)
        if reader is None:
            st.error("Impossible de lire le fichier sélectionné.")
            st.stop()
    else:
        st.info("Aucun fichier CSV sélectionné.")
        st.stop()

    # -- Traitement relances et affichage --

    type_mapping = {
        "TPSV": "Securite Sociale",
        "TPMV": "Mutuelle",
        "VIR": "Client"
    }

    st.markdown("<h1 style='color: #5872fb;'>LISTE DES FACTURES</h1>", unsafe_allow_html=True)

    types_disponibles = set()
    for row in reader:
        type_brut = row.get("Type", "").strip()
        if type_brut == "CHQ-DIFF":
            continue
        type_interprete = type_mapping.get(type_brut, type_brut)
        if type_interprete:
            types_disponibles.add(type_interprete)
    types_disponibles = sorted(types_disponibles)

    # Mettre les filtres dans un expander
    with st.expander("🔍 Filtres", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            type_selection = st.multiselect(
                "Type de facture", 
                options=types_disponibles, 
                default=types_disponibles
            )
            
            temporalites_disponibles = [
                "Futur ✅",
                "Ce mois 🟠",
                "1-3 mois 🔴",
                "> 3 mois 🟣"
            ]
            filtre_temporalites = st.multiselect(
                "Date de facture",
                options=temporalites_disponibles,
                default=temporalites_disponibles
            )
        
        with col2:
            filtrer_non_relances = st.checkbox(
                "Afficher uniquement les factures jamais relancées", 
                value=False
            )

    def get_couleur_et_emoji(date_str):
        try:
            facture_date = datetime.strptime(date_str, "%d/%m/%Y")
            aujourd_hui = datetime.today()
            delta = (aujourd_hui - facture_date).days

            if facture_date > aujourd_hui:
                return "✅", "VERT", "Futur ✅"
            elif 0 <= delta <= 30:
                return "🟠", "ORANGE", "Ce mois 🟠"
            elif 30 < delta <= 90:
                return "🔴", "ROUGE", "1-3 mois 🔴"
            else:
                return "🟣", "VIOLET", "> 3 mois 🟣"
        except:
            return "❓", "INCONNUE", "Inconnue"

    compteur = 0
    for row in reader:
        type_brut = row.get("Type", "").strip()
        if type_brut == "CHQ-DIFF":
            continue
            
        numero_facture = None
        for key in row.keys():
            if "facture" in key.lower():
                numero_facture = row.get(key)
                break
        if not numero_facture or not numero_facture.strip():
            numero_facture = f"INCONNU_{compteur}"
        else:
            numero_facture = numero_facture.strip()

        tp = row.get("TP", "").strip()
        client = row.get("Client", "").strip()
        type_interprete = type_mapping.get(type_brut, type_brut)
        montant = row.get("Montant", "").strip()
        date = row.get("Date", "").strip()
        historique_relances = relances.get(numero_facture, [])

        emoji, couleur, temporalite = get_couleur_et_emoji(date)

        if type_interprete not in type_selection:
            continue
        if filtrer_non_relances and historique_relances:
            continue
        if temporalite not in filtre_temporalites:
            continue

        derniere_relance = historique_relances[-1] if historique_relances else None
        commentaire_relance = f"💬 _{derniere_relance['commentaire']}_ — **{derniere_relance['prenom']}**, {derniere_relance['date']}" if derniere_relance else "_Jamais relancée_"

        titre = f"{emoji} {date} — Facture {numero_facture} — **{client}** — {montant} €\n\n{commentaire_relance}"

        with st.expander(titre):
            st.write(f"**Type :** {type_interprete}")
            st.write(f"**Date :** {date}")
            if tp:
                st.write(f"**Tiers Payeur :** {tp}")
            else:
                st.write(f"**Client :** {client}")

            if historique_relances:
                st.markdown("### 🔁 Historique des relances")
                for r in historique_relances:
                    st.markdown(f"**{r['date']} — {r['prenom']}**  \n💬 _{r['commentaire']}_")

            with st.form(key=f"form_{numero_facture}_{compteur}"):
                date_relance = st.date_input("📅 Nouvelle date de relance", datetime.today())
                commentaire = st.text_area("💬 Commentaire")
                submit = st.form_submit_button("💾 Ajouter la relance")

                if submit:
                    if not commentaire:
                        st.error("Tous les champs sont obligatoires.")
                    else:
                        nouvelle_relance = {
                            "date": date_relance.strftime("%d/%m/%Y"),
                            "prenom": USER,
                            "commentaire": commentaire
                        }
                        if numero_facture not in relances:
                            relances[numero_facture] = []
                        relances[numero_facture].append(nouvelle_relance)

                        try:
                            with open(fichier_relances, "w", encoding="utf-8") as f:
                                json.dump(relances, f, ensure_ascii=False, indent=2)
                            st.success("Relance ajoutée et sauvegardée !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur lors de la sauvegarde : {e}")

        compteur += 1

    # Affichage historique uploads dans la sidebar
    if uploads:
        st.sidebar.markdown("### Historique des listes")
        
        # Créer un dictionnaire pour compter les uploads par utilisateur
        upload_counts = {}
        for i, up in enumerate(reversed(uploads[-10:]), 1):
            user = up.get('user', 'N/A')
            if user not in upload_counts:
                upload_counts[user] = 0
            upload_counts[user] += 1
            count = upload_counts[user]
            
            # Formater la date plus joliment
            dt_str = up['datetime']
            if " à " in dt_str:
                date_part, time_part = dt_str.split(" à ")
                dt_obj = datetime.strptime(date_part + time_part, "%Y%m%d%H%M%S")
                formatted_date = dt_obj.strftime("%d/%m à %H:%M")
            else:
                formatted_date = dt_str
                
            # Afficher avec un nom simplifié "Liste X"
            st.sidebar.markdown(
                f"**Liste {len(uploads)-i+1}** (par {user})  \n"
                f"<small>{formatted_date}</small>  \n"
                f"<small><code>{up['filename']}</code></small>",
                unsafe_allow_html=True
            )

    # Graphique des factures par mois
    dates = []
    for row in reader:
        type_brut = row.get("Type", "").strip()
        if type_brut == "CHQ-DIFF":
            continue
            
        date_str = row.get("Date", "").strip()
        try:
            date_dt = datetime.strptime(date_str, "%d/%m/%Y")
            dates.append(date_dt)
        except:
            pass

    if dates:
        df = pd.DataFrame({"date": dates})
        df["mois"] = df["date"].dt.to_period("M").dt.to_timestamp()
        df_count_month = df.groupby("mois").size().reset_index(name="nombre_factures")

        st.markdown("## 📈 Étalement des factures dans le temps (par mois)")

        fig = px.bar(
            df_count_month,
            x="mois",
            y="nombre_factures",
            labels={"mois": "Mois", "nombre_factures": "Nombre de factures"},
            title="Nombre de factures par mois",
            color_discrete_sequence=['gray']
        )

        fig.update_layout(
            xaxis=dict(tickformat="%b %Y"),
            yaxis=dict(title="Nombre de factures"),
            coloraxis_showscale=False,
            plot_bgcolor="white",
            font=dict(size=14)
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucune date valide trouvée dans les factures pour générer le graphique.")

# --- Onglet Relance Devis ---
elif st.session_state.current_tab == "Relance Devis":
    st.markdown("<h1 style='color: #5872fb;'>RELANCE DEVIS</h1>", unsafe_allow_html=True)
    
    # Formulaire pour ajouter un nouveau devis
    with st.form(key="form_nouveau_devis"):
        st.markdown("### Ajouter un nouveau devis")
        col1, col2 = st.columns(2)
        
        with col1:
            prenom = st.text_input("Prénom")
            nom = st.text_input("Nom")
            email = st.text_input("Email")
            
        with col2:
            telephone = st.text_input("Téléphone")
            date_devis = st.date_input("Date du devis", datetime.today())
            commentaire = st.text_area("Commentaire")
        
        submit = st.form_submit_button("💾 Enregistrer le devis")
        
        if submit:
            if not prenom or not nom or not email or not telephone:
                st.error("Les champs Prénom, Nom, Email et Téléphone sont obligatoires.")
            else:
                nouveau_devis = {
                    "prenom": prenom,
                    "nom": nom,
                    "email": email,
                    "telephone": telephone,
                    "date_devis": date_devis.strftime("%d/%m/%Y"),
                    "commentaire": commentaire,
                    "relances": [],
                    "date_creation": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "createur": USER
                }
                
                devis.append(nouveau_devis)
                with open(devis_file, "w", encoding="utf-8") as f:
                    json.dump(devis, f, ensure_ascii=False, indent=2)
                st.success("Devis ajouté avec succès !")
                st.rerun()
    
    # Liste des devis existants
    st.markdown("### Liste des devis")
    
    if not devis:
        st.info("Aucun devis enregistré pour le moment.")
    else:
        # Options de tri
        col1, col2 = st.columns(2)
        with col1:
            tri_par = st.selectbox("Trier par", ["Nom", "Date du devis"])
        
        with col2:
            ordre_tri = st.selectbox("Ordre", ["Croissant", "Décroissant"])
        
        # Trier les devis
        if tri_par == "Nom":
            devis_tries = sorted(
                devis,
                key=lambda x: f"{x['nom'].lower()} {x['prenom'].lower()}",
                reverse=(ordre_tri == "Décroissant")
            )
        else:
            devis_tries = sorted(
                devis,
                key=lambda x: datetime.strptime(x["date_devis"], "%d/%m/%Y"),
                reverse=(ordre_tri == "Décroissant")
            )
        
        # Afficher chaque devis
        for idx, d in enumerate(devis_tries):
            derniere_relance = d["relances"][-1] if d["relances"] else None
            commentaire_relance = (
                f"💬 _{derniere_relance['commentaire']}_ — **{derniere_relance['prenom']}**, {derniere_relance['date']}"
                if derniere_relance else "_Jamais relancé_"
            )
            
            with st.expander(f"📅 {d['date_devis']} — {d['prenom']} {d['nom']} — {d['email']} — {d['telephone']}\n\n{commentaire_relance}"):
                st.write(f"**Email:** {d['email']}")
                st.write(f"**Téléphone:** {d['telephone']}")
                st.write(f"**Date du devis:** {d['date_devis']}")
                st.write(f"**Commentaire:** {d['commentaire']}")
                st.write(f"**Créé le:** {d['date_creation']} par {d['createur']}")
                
                if d["relances"]:
                    st.markdown("### 🔁 Historique des relances")
                    for r in d["relances"]:
                        st.markdown(f"**{r['date']} — {r['prenom']}**  \n💬 _{r['commentaire']}_")
                
                # Formulaire pour ajouter une relance
                with st.form(key=f"form_relance_devis_{idx}"):
                    date_relance = st.date_input("📅 Nouvelle date de relance", datetime.today(), key=f"date_relance_{idx}")
                    commentaire_relance = st.text_area("💬 Commentaire", key=f"commentaire_relance_{idx}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        submit_relance = st.form_submit_button("💾 Ajouter la relance")
                    
                    with col2:
                        if st.form_submit_button("🗑️ Supprimer ce devis"):
                            # Trouver l'index original dans la liste devis (pas dans devis_tries)
                            original_idx = next(i for i, item in enumerate(devis) if item["date_creation"] == d["date_creation"])
                            devis.pop(original_idx)
                            with open(devis_file, "w", encoding="utf-8") as f:
                                json.dump(devis, f, ensure_ascii=False, indent=2)
                            st.success("Devis supprimé avec succès !")
                            st.rerun()
                    
                    if submit_relance:
                        if not commentaire_relance:
                            st.error("Tous les champs sont obligatoires.")
                        else:
                            nouvelle_relance = {
                                "date": date_relance.strftime("%d/%m/%Y"),
                                "prenom": USER,
                                "commentaire": commentaire_relance
                            }
                            d["relances"].append(nouvelle_relance)
                            with open(devis_file, "w", encoding="utf-8") as f:
                                json.dump(devis, f, ensure_ascii=False, indent=2)
                            st.success("Relance ajoutée avec succès !")
                            st.rerun()