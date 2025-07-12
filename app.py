import csv
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
import streamlit as st
import os
from PIL import Image
import pandas as pd
import plotly.express as px
import base64


st.set_page_config(
    page_title="Pingster",  # Titre qui apparaîtra dans l'onglet
    page_icon="icon.png",  # Emoji ou chemin vers une image
    layout="wide"  # Optionnel: layout de la page
)

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

PRIMES_FILE = GROUP_FOLDER / "primes.json"


def load_primes():
    if PRIMES_FILE.exists():
        try:
            with open(PRIMES_FILE, encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"ventes": [], "taux": 10}  # Valeur par défaut 10%
    return {"ventes": [], "taux": 10}

def save_primes(data):
    with open(PRIMES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
    [ "Tableau de Bord", "Relance Devis", "Relance Facture", "Suivi des primes","Suivi des tâches"],  # Ajout du nouvel onglet
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

# --- Nouvel Onglet Tableau de Bord ---
elif st.session_state.current_tab == "Tableau de Bord":
    st.markdown("<h1 style='color: #5872fb;'>TABLEAU DE BORD</h1>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)  # Espace ajouté ici
    
    # Dictionnaire de mapping des types
    type_mapping = {
        "TPSV": "Securite Sociale",
        "TPMV": "Mutuelle",
        "VIR": "Client"
    }
    
    # Charger le dernier fichier uploadé pour les factures impayées
    dernier_fichier = uploads[-1]["filename"] if uploads else None
    
    # Charger les données des factures si disponible
    if dernier_fichier:
        csv_path = GROUP_FOLDER / dernier_fichier
        try:
            with open(csv_path, encoding="ISO-8859-1") as f:
                toutes_lignes = []
                for line in f:
                    line = line.strip()
                    if "total" in line.lower():
                        break
                    toutes_lignes.append(line)
            
            idx_entete = next((i for i, l in enumerate(toutes_lignes) if "facture" in l.lower()), None)
            if idx_entete is None:
                st.error("En-tête introuvable dans le CSV.")
                reader = None
            else:
                lignes_utiles = toutes_lignes[idx_entete:]
                reader = list(csv.DictReader(lignes_utiles, delimiter=";"))
        except Exception as e:
            st.error(f"Erreur lecture fichier CSV : {e}")
            reader = None
    else:
        reader = None
        st.warning("Aucun fichier de facture n'a été uploadé.")
    
    if reader:
        # Calcul des factures impayées
        factures_impayees = []
        montant_total = 0
        repartition = {"Client": 0, "Mutuelle": 0, "Securite Sociale": 0, "Autre": 0}
        anciennetes = {"< 30j": 0, "30-90j": 0, "> 90j": 0, "Futur": 0}
        
        for row in reader:
            type_brut = row.get("Type", "").strip()
            if type_brut == "CHQ-DIFF":
                continue
                
            # Récupérer les infos de la facture
            numero_facture = None
            for key in row.keys():
                if "facture" in key.lower():
                    numero_facture = row.get(key)
                    break
            if not numero_facture:
                continue
                
            type_interprete = type_mapping.get(type_brut, "Autre")
            montant_str = row.get("Montant", "0").replace(",", ".").strip()
            try:
                montant = float(montant_str)
            except:
                montant = 0
                
            date_str = row.get("Date", "")
            try:
                date_facture = datetime.strptime(date_str, "%d/%m/%Y")
                delta = (datetime.now() - date_facture).days
                
                if date_facture > datetime.now():
                    anciennete = "Futur"
                elif delta <= 30:
                    anciennete = "< 30j"
                elif 30 < delta <= 90:
                    anciennete = "30-90j"
                else:
                    anciennete = "> 90j"
            except:
                anciennete = "Inconnue"
            
            factures_impayees.append({
                "numero": numero_facture,
                "type": type_interprete,
                "montant": montant,
                "date": date_str,
                "anciennete": anciennete,
                "client": row.get("Client", "")
            })
            
            montant_total += montant
            repartition[type_interprete] = repartition.get(type_interprete, 0) + montant
            if anciennete in anciennetes:
                anciennetes[anciennete] += montant
        
        # Afficher les KPI
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; text-align: center;">
                <h3 style="color: #5872fb; margin-top: 0;">Factures impayées</h3>
                <p style="font-size: 24px; font-weight: bold; margin-bottom: 0;">{}</p>
            </div>
            """.format(len(factures_impayees)), unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; text-align: center;">
                <h3 style="color: #5872fb; margin-top: 0;">Montant total dû</h3>
                <p style="font-size: 24px; font-weight: bold; margin-bottom: 0;">{:.2f} €</p>
            </div>
            """.format(montant_total), unsafe_allow_html=True)
        
        with col3:
            relance_count = sum(len(v) for v in relances.values())
            st.markdown("""
            <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; text-align: center;">
                <h3 style="color: #5872fb; margin-top: 0;">Relances facture</h3>
                <p style="font-size: 24px; font-weight: bold; margin-bottom: 0;">{}</p>
            </div>
            """.format(relance_count), unsafe_allow_html=True)
        
        # Graphiques
        st.markdown("<br>", unsafe_allow_html=True)  # Espace ajouté ici avant le titre
        st.markdown("### Répartition par type")
        df_repartition = pd.DataFrame({
            "Type": list(repartition.keys()),
            "Montant": list(repartition.values())
        })
        
        fig_repartition = px.pie(
            df_repartition,
            names="Type",
            values="Montant",
            color_discrete_sequence=['#5872fb', '#8a9eff', '#c0c9ff', '#e0e4ff'],
            hole=0.4
        )
        fig_repartition.update_traces(
            textposition='inside',
            textinfo='percent+label',
            textfont_size=14
        )
        fig_repartition.update_layout(
            showlegend=False,
            margin=dict(l=20, r=20, t=30, b=20)
        )
        
        st.plotly_chart(fig_repartition, use_container_width=True)
        
        st.markdown("### Ancienneté des factures impayées")
        df_anciennete = pd.DataFrame({
            "Ancienneté": list(anciennetes.keys()),
            "Montant": list(anciennetes.values())
        })
        
        fig_anciennete = px.bar(
            df_anciennete,
            x="Ancienneté",
            y="Montant",
            color_discrete_sequence=['#5872fb']*4,
            text="Montant"
        )
        fig_anciennete.update_traces(
            texttemplate='%{y:.2f} €',
            textposition='outside',
            marker_line_width=0,
            marker_color='#5872fb'
        )
        fig_anciennete.update_layout(
            showlegend=False,
            xaxis_title=None,
            yaxis_title="Montant (€)",
            uniformtext_minsize=12,
            plot_bgcolor="white"
        )
        
        st.plotly_chart(fig_anciennete, use_container_width=True)
    
    # --- Paramètres du tableau de bord ---
    with st.expander("Paramètres du classement", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            periode_options = {
                "Ce mois": 30,
                "3 derniers mois": 90,
                "6 derniers mois": 180,
                "Cette année": 365,
                "Toutes les données": None
            }
            selected_periode = st.selectbox(
                "Période d'analyse",
                options=list(periode_options.keys()),
                index=0
            )
            jours_retour = periode_options[selected_periode]
        
        with col2:
            type_relance = st.radio(
                "Type de relance à analyser",
                options=["Factures", "Devis", "Les deux"],
                index=2
            )
    
    # --- Section Classement des relances ---
    
    # Charger toutes les données de relances
    def charger_relances_factures():
        relances_factures = []
        if fichier_relances.exists():
            try:
                with open(fichier_relances, encoding="utf-8") as f:
                    contenu = f.read().strip()
                    if contenu:
                        raw = json.loads(contenu)
                        for facture, relances_list in raw.items():
                            for relance in relances_list:
                                relance["type"] = "Facture"
                                relances_factures.append(relance)
            except json.JSONDecodeError:
                pass
        return relances_factures
    
    def charger_relances_devis():
        relances_devis = []
        if devis_file.exists():
            try:
                with open(devis_file, encoding="utf-8") as f:
                    devis_data = json.load(f)
                    for devis in devis_data:
                        for relance in devis.get("relances", []):
                            relance["type"] = "Devis"
                            relances_devis.append(relance)
            except:
                pass
        return relances_devis
    
    # Fusionner les relances selon la sélection
    toutes_relances = []
    
    if type_relance in ["Factures", "Les deux"]:
        toutes_relances.extend(charger_relances_factures())
    
    if type_relance in ["Devis", "Les deux"]:
        toutes_relances.extend(charger_relances_devis())
    
    # Filtrer par période si nécessaire
    if jours_retour is not None:
        date_limite = datetime.now() - timedelta(days=jours_retour)
        toutes_relances = [
            r for r in toutes_relances 
            if datetime.strptime(r["date"], "%d/%m/%Y") >= date_limite
        ]
    
    # Récupérer tous les utilisateurs du magasin
    tous_utilisateurs = [user for user, data in users.items() if data.get("magasin", "").lower() == MAGASIN]
    
    # Compter les relances par utilisateur
    comptage_relances = {user: 0 for user in tous_utilisateurs}
    for relance in toutes_relances:
        utilisateur = relance["prenom"]
        if utilisateur in comptage_relances:
            comptage_relances[utilisateur] += 1
    
    # Créer le dataframe trié
    df = pd.DataFrame({
        "Utilisateur": list(comptage_relances.keys()),
        "Relances": list(comptage_relances.values())
    }).sort_values("Relances", ascending=False)
    
    # --- Top 3 avec photos et couronnes ---
    st.markdown("### 🏆 Top 3 des relanceurs")
    
    if len(df) > 0:
        # Créer 3 colonnes pour le top 3
        col1, col2, col3 = st.columns(3)
        
        # Fonction pour afficher un membre du podium
        def display_podium_member(col, user, count, position, crown_color):
            with col:
                # Récupérer la photo de profil
                profile_pic = get_profile_picture(user)
                img_base64 = base64.b64encode(open(profile_pic, "rb").read()).decode()
                
                # Style CSS pour la carte
                st.markdown(f"""
                <div style="
                    background-color: #f0f2f6;
                    border-radius: 15px;
                    padding: 20px;
                    text-align: center;
                    margin-bottom: 20px;
                    position: relative;
                    border: 2px solid {crown_color};
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                ">
                    <div style="
                        position: absolute;
                        top: -15px;
                        left: 50%;
                        transform: translateX(-50%);
                        font-size: 24px;
                    ">
                        {position}
                    </div>
                    <img src="data:image/png;base64,{img_base64}" 
                         style="
                             width: 100px;
                             height: 100px;
                             border-radius: 50%;
                             object-fit: cover;
                             border: 3px solid {crown_color};
                             margin: 10px auto;
                         ">
                    <h3 style="color: #5872fb; margin: 10px 0 5px 0;">{user}</h3>
                    <p style="font-size: 18px; font-weight: bold; margin: 0;">{count} relances</p>
                </div>
                """, unsafe_allow_html=True)
        
        # Afficher le top 3
        top3 = df.head(3)
        
        # 1ère place (or)
        if len(top3) >= 1:
            display_podium_member(col2, top3.iloc[0]["Utilisateur"], top3.iloc[0]["Relances"], "👑", "#FFD700")
        
        # 2ème place (argent)
        if len(top3) >= 2:
            display_podium_member(col1, top3.iloc[1]["Utilisateur"], top3.iloc[1]["Relances"], "🥈", "#C0C0C0")
        
        # 3ème place (bronze)
        if len(top3) >= 3:
            display_podium_member(col3, top3.iloc[2]["Utilisateur"], top3.iloc[2]["Relances"], "🥉", "#CD7F32")
    
    # Layout avec tableau à gauche et graphique à droite
    st.markdown("### Détails du classement")
    col_table, col_graph = st.columns([1, 1])
    
    with col_table:
        # Style pour le tableau
        styled_df = df.sort_values("Relances", ascending=False).style \
            .apply(lambda x: ['color: #5872fb; font-weight: bold' for i in x], subset=['Relances']) \
            .format({'Relances': '{:.0f}'}) \
            .set_properties(**{
                'text-align': 'left',
                'font-size': '16px'
            })
        
        st.dataframe(
            styled_df,
            use_container_width=True,
            height=(len(df) + 1) * 35 + 3,
            hide_index=True
        )
        
        st.markdown(f"**Total relances:** {len(toutes_relances)}")
    
    with col_graph:
        # Graphique horizontal avec couleur unique
            
        fig = px.bar(
            df,
            x="Relances",
            y="Utilisateur",
            orientation='h',
            color_discrete_sequence=['#5872fb'],
            text="Relances",
            height=max(400, 50 * len(df)))
        
        # Personnalisation
        fig.update_layout(
            showlegend=False,
            xaxis_title=None,
            yaxis_title=None,
            plot_bgcolor="white",
            margin=dict(l=20, r=20, t=30, b=20),
            yaxis={'categoryorder':'total ascending'},
            uniformtext_minsize=12,
            uniformtext_mode='hide')
        
        fig.update_traces(
            texttemplate='%{x}',
            textposition='outside',
            textfont_size=14,
            marker_color='#5872fb',
            marker_line_color='#5872fb',
            marker_line_width=1)
        
        st.plotly_chart(fig, use_container_width=True, use_container_height=True)


# --- Onglet Suivi des primes ---
elif st.session_state.current_tab == "Suivi des primes":
    st.markdown("<h1 style='color: #5872fb;'>SUIVI DES PRIMES</h1>", unsafe_allow_html=True)
    
    primes_data = load_primes()

    taux_prime = primes_data.get("taux", 10)
    ventes = primes_data.get("ventes", [])
    
    # Vérifier si l'utilisateur est un éditeur
    is_editeur = users.get(USER, {}).get("type") == "editeur"
    
    if is_editeur:
        with st.expander("➕ Ajouter une vente de carte"):
            with st.form(key="form_ajout_vente"):
                # Sélectionner le vendeur (uniquement ceux du même magasin)
                vendeurs_magasin = [u for u, data in users.items() 
                                  if data.get("magasin", "").lower() == MAGASIN 
                                  and u != USER]  # Exclure l'éditeur lui-même
                
                vendeur = st.selectbox("Vendeur", options=vendeurs_magasin)
                date_vente = st.date_input("Date de vente", datetime.today())
                type_carte = st.selectbox("Type de carte", 
                                        ["Little Acuitis Or", "Tranquillité Or Optique", "Tranquillité Audio"])
                
                if st.form_submit_button("Enregistrer la vente"):
                    nouvelle_vente = {
                        "vendeur": vendeur,
                        "date": date_vente.strftime("%d/%m/%Y"),
                        "type": type_carte,
                        "enregistree_par": USER,
                        "timestamp": datetime.now().isoformat()
                    }
                    ventes.append(nouvelle_vente)
                    primes_data["ventes"] = ventes
                    save_primes(primes_data)
                    st.success("Vente enregistrée avec succès !")
                    st.rerun()
        
        with st.expander("⚙️ Paramètres des primes"):
            with st.form(key="form_taux_prime"):
                nouveau_taux = st.slider("Taux de prime (%)", min_value=0, max_value=100, value=taux_prime)
                if st.form_submit_button("Enregistrer le taux"):
                    primes_data["taux"] = nouveau_taux
                    save_primes(primes_data)
                    st.success(f"Taux de prime mis à jour à {nouveau_taux}%")
                    st.rerun()
    
    # Calcul des primes par mois
    st.markdown("## Calcul des primes")
    
    # Prix des cartes
    prix_cartes = {
        "Little Acuitis Or": 30,
        "Tranquillité Or Optique": 45,
        "Tranquillité Audio": 150
    }
    
    # Sélection du mois à afficher
    mois_courant = datetime.now().strftime("%m/%Y")
    mois_disponibles = set()
    
    for vente in ventes:
        try:
            date_obj = datetime.strptime(vente["date"], "%d/%m/%Y")
            mois_disponibles.add(date_obj.strftime("%m/%Y"))
        except:
            pass
    
    mois_disponibles = sorted(mois_disponibles, reverse=True)
    if mois_courant not in mois_disponibles:
        mois_disponibles.insert(0, mois_courant)
    
    mois_selectionne = st.selectbox("Mois à afficher", options=mois_disponibles, index=0)
    
    # Filtrer les ventes du mois sélectionné
    ventes_mois = []
    for vente in ventes:
        try:
            date_obj = datetime.strptime(vente["date"], "%d/%m/%Y")
            if date_obj.strftime("%m/%Y") == mois_selectionne:
                ventes_mois.append(vente)
        except:
            pass
    
    # Calculer le total des primes
    total_prime = 0
    details_ventes = []
    
    for vente in ventes_mois:
        type_carte = vente["type"]
        prix = prix_cartes.get(type_carte, 0)
        prime = prix * (taux_prime / 100)
        total_prime += prime
        
        details_ventes.append({
            "Vendeur": vente["vendeur"],
            "Date": vente["date"],
            "Type de carte": type_carte,
            "Prix (€)": prix,
            "Prime (€)": prime,  # Stocker directement le float au lieu d'un string formaté
            "Enregistrée par": vente.get("enregistree_par", "N/A")
        })
    
    # Afficher le total
    st.metric("Total des primes du mois", f"{total_prime:.2f} €")
    
    # Afficher le détail des ventes
    if details_ventes:
        df = pd.DataFrame(details_ventes)
        styled_df = df.style.format({
            "Prix (€)": "{:.2f} €",
            "Prime (€)": "{:.2f} €"
        })
        st.dataframe(styled_df, hide_index=True, use_container_width=True)

# --- Onglet Suivi des tâches ---
elif st.session_state.current_tab == "Suivi des tâches":
    st.markdown("<h1 style='color: #5872fb;'>SUIVI DES TÂCHES</h1>", unsafe_allow_html=True)
    
    # Fichier de stockage des tâches
    TACHES_FILE = GROUP_FOLDER / "taches.json"
    
    # Charger les tâches existantes
    def load_taches():
        if TACHES_FILE.exists():
            try:
                with open(TACHES_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {"actives": [], "archivees": []}
        return {"actives": [], "archivees": []}
    
    def save_taches(data):
        with open(TACHES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    taches_data = load_taches()
    taches_actives = taches_data.get("actives", [])
    taches_archivees = taches_data.get("archivees", [])
    
    # Formulaire pour créer une nouvelle tâche
    with st.expander("➕ Créer une nouvelle tâche", expanded=True):
        with st.form(key="form_nouvelle_tache"):
            col1, col2 = st.columns(2)
            
            with col1:
                titre = st.text_input("Titre de la tâche*", help="Titre clair et descriptif")
                description = st.text_area("Description*")
                priorite = st.selectbox("Priorité*", ["Haute", "Moyenne", "Basse"])
                
            with col2:
                date_echeance = st.date_input("Date d'échéance*", min_value=datetime.today())
                attribue_a = st.selectbox(
                    "Attribuée à*", 
                    options=[u for u in users.keys() if users[u]["magasin"].lower() == MAGASIN],
                    index=0
                )
                createur = USER  # Récupéré automatiquement
            
            submit = st.form_submit_button("💾 Créer la tâche")
            
            if submit:
                if not titre or not description:
                    st.error("Les champs avec * sont obligatoires.")
                else:
                    nouvelle_tache = {
                        "id": str(datetime.now().timestamp()),
                        "titre": titre,
                        "description": description,
                        "priorite": priorite,
                        "date_creation": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "date_echeance": date_echeance.strftime("%d/%m/%Y"),
                        "attribue_a": attribue_a,
                        "createur": createur,
                        "statut": "En cours",
                        "modifications": [{
                            "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "utilisateur": createur,
                            "action": "Création de la tâche"
                        }]
                    }
                    
                    taches_actives.append(nouvelle_tache)
                    taches_data["actives"] = taches_actives
                    save_taches(taches_data)
                    st.success("Tâche créée avec succès !")
                    st.rerun()
    
    # Filtres pour les tâches
    with st.expander("🔍 Filtres", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filtre_attribue = st.multiselect(
                "Attribuée à",
                options=list(set([u for u in users.keys() if users[u]["magasin"].lower() == MAGASIN])),
                default=[]
            )
            
        with col2:
            filtre_createur = st.multiselect(
                "Créée par",
                options=list(set([u for u in users.keys() if users[u]["magasin"].lower() == MAGASIN])),
                default=[]
            )
            
        with col3:
            filtre_priorite = st.multiselect(
                "Priorité",
                options=["Haute", "Moyenne", "Basse"],
                default=["Haute", "Moyenne", "Basse"]
            )
    
    # Fonction pour déterminer le statut de la tâche
    def get_tache_statut(tache):
        if tache.get("statut") == "Terminée":
            return "Terminée"
        
        try:
            echeance = datetime.strptime(tache["date_echeance"], "%d/%m/%Y")
            aujourdhui = datetime.today()
            
            if echeance < aujourdhui:
                return "En retard"
            elif (echeance - aujourdhui).days <= 2:
                return "À faire bientôt"
            else:
                return "En cours"
        except:
            return "En cours"
    
    # Afficher les tâches actives filtrées
    st.markdown("## Tâches en cours")
    
    taches_filtrees = []
    for tache in taches_actives:
        # Appliquer les filtres
        if filtre_attribue and tache["attribue_a"] not in filtre_attribue:
            continue
        if filtre_createur and tache["createur"] not in filtre_createur:
            continue
        if filtre_priorite and tache["priorite"] not in filtre_priorite:
            continue
            
        taches_filtrees.append(tache)
    
    if not taches_filtrees:
        st.info("Aucune tâche ne correspond aux filtres sélectionnés.")
    else:
        # Trier les tâches (en retard d'abord, puis par priorité et date d'échéance)
        def sort_key(tache):
            statut = get_tache_statut(tache)
            priority_order = {"Haute": 0, "Moyenne": 1, "Basse": 2}
            
            return (
                0 if statut == "En retard" else 
                1 if statut == "À faire bientôt" else 2,
                priority_order[tache["priorite"]],
                datetime.strptime(tache["date_echeance"], "%d/%m/%Y")
            )
        
        taches_filtrees.sort(key=sort_key)
        
        for tache in taches_filtrees:
            statut = get_tache_statut(tache)
            
            # Déterminer la couleur en fonction du statut
            if statut == "En retard":
                border_color = "#ff4b4b"
                statut_text = "🟠 EN RETARD"
            elif statut == "À faire bientôt":
                border_color = "#ffa500"
                statut_text = "🔜 À FAIRE BIENTÔT"
            else:
                border_color = "#5872fb"
                statut_text = "🟢 EN COURS"
            
            with st.container(border=True):
                # En-tête de la tâche
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"### {tache['titre']}")
                    
                with col2:
                    st.markdown(f"""
                    <div style="
                        background-color: #f0f2f6;
                        padding: 5px 10px;
                        border-radius: 20px;
                        text-align: center;
                        border: 1px solid {border_color};
                        color: {border_color};
                        font-weight: bold;
                    ">
                        {statut_text}
                    </div>
                    """, unsafe_allow_html=True)
                
                # Détails de la tâche
                col_details1, col_details2 = st.columns(2)
                
                with col_details1:
                    st.markdown(f"""
                    - **Priorité:** {tache['priorite']}
                    - **Créée par:** {tache['createur']}
                    - **Date création:** {tache['date_creation']}
                    """)
                
                with col_details2:
                    st.markdown(f"""
                    - **Attribuée à:** {tache['attribue_a']}
                    - **Échéance:** {tache['date_echeance']}
                    - **Statut:** {tache.get('statut', 'En cours')}
                    """)
                
                # Description et actions
                with st.expander("📝 Voir la description et les actions"):
                    st.markdown(f"**Description:**  \n{tache['description']}")
                    
                    # Historique des modifications
                    if tache.get("modifications"):
                        st.markdown("---")
                        st.markdown("### 📜 Historique des modifications")
                        for mod in reversed(tache["modifications"]):
                            st.markdown(f"**{mod['date']} — {mod['utilisateur']}**  \n{mod['action']}")
                    
                    # Formulaire de modification
                    with st.form(key=f"form_modif_{tache['id']}"):
                        new_statut = st.selectbox(
                            "Modifier le statut",
                            options=["En cours", "Terminée", "En attente"],
                            index=0 if tache.get("statut") != "Terminée" else 1
                        )
                        
                        new_date_echeance = st.date_input(
                            "Modifier la date d'échéance",
                            value=datetime.strptime(tache["date_echeance"], "%d/%m/%Y")
                        )
                        
                        new_commentaire = st.text_area("Ajouter un commentaire")
                        
                        col_btn1, col_btn2 = st.columns(2)
                        
                        with col_btn1:
                            if st.form_submit_button("💾 Enregistrer les modifications"):
                                # Enregistrer les modifications
                                modification = {
                                    "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                    "utilisateur": USER,
                                    "action": f"Statut changé à '{new_statut}'"
                                }
                                
                                if new_date_echeance.strftime("%d/%m/%Y") != tache["date_echeance"]:
                                    modification["action"] += f", échéance modifiée au {new_date_echeance.strftime('%d/%m/%Y')}"
                                
                                if new_commentaire:
                                    modification["action"] += f" | Commentaire: {new_commentaire}"
                                
                                tache["statut"] = new_statut
                                tache["date_echeance"] = new_date_echeance.strftime("%d/%m/%Y")
                                
                                if "modifications" not in tache:
                                    tache["modifications"] = []
                                tache["modifications"].append(modification)
                                
                                # Si la tâche est terminée, la déplacer dans les archives
                                if new_statut == "Terminée":
                                    taches_actives.remove(tache)
                                    taches_archivees.append(tache)
                                
                                taches_data["actives"] = taches_actives
                                taches_data["archivees"] = taches_archivees
                                save_taches(taches_data)
                                st.success("Tâche mise à jour !")
                                st.rerun()
                        
                        with col_btn2:
                            if st.form_submit_button("🗑️ Supprimer cette tâche"):
                                taches_actives.remove(tache)
                                taches_data["actives"] = taches_actives
                                save_taches(taches_data)
                                st.success("Tâche supprimée !")
                                st.rerun()
    
    # Section archives
    st.markdown("## Tâches archivées")
    
    if not taches_archivees:
        st.info("Aucune tâche archivée pour le moment.")
    else:
        with st.expander("Voir les tâches archivées", expanded=False):
            for tache in reversed(taches_archivees[-20:]):  # Limiter à 20 dernières tâches
                with st.container(border=True):
                    st.markdown(f"### {tache['titre']}")
                    
                    col_arch1, col_arch2 = st.columns(2)
                    
                    with col_arch1:
                        st.markdown(f"""
                        - **Priorité:** {tache['priorite']}
                        - **Créée par:** {tache['createur']}
                        - **Date création:** {tache['date_creation']}
                        """)
                    
                    with col_arch2:
                        st.markdown(f"""
                        - **Attribuée à:** {tache['attribue_a']}
                        - **Échéance:** {tache['date_echeance']}
                        - **Statut:** Terminée
                        """)
                    
                    with st.expander("📝 Voir les détails"):
                        st.markdown(f"**Description:**  \n{tache['description']}")
                        
                        if tache.get("modifications"):
                            st.markdown("---")
                            st.markdown("### Historique des modifications")
                            for mod in reversed(tache["modifications"]):
                                st.markdown(f"**{mod['date']} — {mod['utilisateur']}**  \n{mod['action']}")