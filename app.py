import csv
import json
import hashlib
from pathlib import Path
from datetime import datetime
import streamlit as st
import os
from PIL import Image

# Afficher le logo en sidebar (en haut à gauche)
logo = Image.open("logo.jpg")
st.sidebar.image(logo, width=120)

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

st.sidebar.title("🔐 Connexion")

if "username" not in st.session_state:
    st.session_state.username = None

if st.session_state.username is None:
    username_input = st.sidebar.text_input("Nom d'utilisateur")
    password_input = st.sidebar.text_input("Mot de passe", type="password")
    if st.sidebar.button("Se connecter"):
        username_input = username_input.strip().lower()
        if not username_input:
            st.sidebar.error("Merci d'entrer un nom d'utilisateur.")
        elif username_input not in users:
            st.sidebar.error("Utilisateur inconnu.")
        else:
            # Vérifier mot de passe
            if hash_password(password_input) == users[username_input]["password_hash"]:
                st.session_state.username = username_input
                st.rerun()
            else:
                st.sidebar.error("Mot de passe incorrect.")
else:
    st.sidebar.write(f"Connecté en tant que **{st.session_state.username}**")
    if st.sidebar.button("Se déconnecter"):
        st.session_state.username = None
        st.rerun()

if st.session_state.username is None:
    st.stop()

USER = st.session_state.username
VILLE = users[USER]["ville"].lower()

# -- Dossier commun au groupe (ville) --
GROUP_FOLDER = Path("users") / VILLE
GROUP_FOLDER.mkdir(parents=True, exist_ok=True)

# -- Gestion des relances partagées au niveau de la ville --
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
                st.info(f"🔄 Relances chargées pour la ville : {VILLE}.")
    except json.JSONDecodeError:
        st.warning("⚠️ Fichier relances.json invalide, il sera écrasé à la prochaine sauvegarde.")

# -- Gestion historique uploads partagés (ville) --
uploads_file = GROUP_FOLDER / "uploads.json"
uploads = []
if uploads_file.exists():
    try:
        with open(uploads_file, encoding="utf-8") as f:
            uploads = json.load(f)
    except:
        uploads = []

# -- Upload du fichier CSV --
uploaded_file = st.file_uploader("📤 Dépose ton fichier CSV ici", type="csv")

if uploaded_file:
    # Sauvegarde du fichier uploadé dans dossier commun ville
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{now_str}_{uploaded_file.name}"
    file_path = GROUP_FOLDER / filename
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getvalue())
    st.success(f"Fichier sauvegardé : {filename}")

    # Mise à jour historique uploads commun
    uploads.append({"filename": filename, "datetime": now_str})
    with open(uploads_file, "w", encoding="utf-8") as f:
        json.dump(uploads, f, ensure_ascii=False, indent=2)

    # Lecture du CSV uploadé pour affichage et traitement
    toutes_lignes = []
    for line in uploaded_file:
        line = line.decode("ISO-8859-1").strip()
        if "total" in line.lower():
            break
        toutes_lignes.append(line)

    idx_entete = next((i for i, l in enumerate(toutes_lignes) if "facture" in l.lower()), None)
    if idx_entete is None:
        st.error("❌ En-tête introuvable dans le CSV.")
        st.stop()
    lignes_utiles = toutes_lignes[idx_entete:]
    reader = list(csv.DictReader(lignes_utiles, delimiter=";"))

    # -- Traitement relances et affichage --

    type_mapping = {
        "TPSV": "secu",
        "TPMV": "mutuelle",
        "VIR": "client"
    }

    st.title(f"📋 Gestion des Relances - Utilisateur : {USER} | {VILLE.capitalize()}")

    types_disponibles = set()
    for row in reader:
        type_brut = row.get("Type", "").strip()
        type_interprete = type_mapping.get(type_brut, type_brut)
        if type_interprete:
            types_disponibles.add(type_interprete)
    types_disponibles = sorted(types_disponibles)

    type_selection = st.multiselect("🔍 Filtrer par type", options=types_disponibles, default=types_disponibles)
    filtrer_non_relances = st.checkbox("❗ Afficher uniquement les factures jamais relancées", value=False)

    temporalites_disponibles = [
        "Futur ✅",
        "Ce mois 🟠",
        "1-3 mois 🔴",
        "> 3 mois 🟣"
    ]
    filtre_temporalites = st.multiselect(
        "⏱️ Filtrer par date de facture",
        options=temporalites_disponibles,
        default=temporalites_disponibles
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
        type_brut = row.get("Type", "").strip()
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

        titre = f"{emoji} {date} — Facture {numero_facture} — {montant} €"

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
                date_relance = st.text_input("📅 Nouvelle date de relance (jj/mm/aaaa)")
                prenom = st.text_input("👤 Prénom")
                commentaire = st.text_area("💬 Commentaire")
                submit = st.form_submit_button("💾 Ajouter la relance")

                if submit:
                    if not date_relance or not prenom or not commentaire:
                        st.error("Tous les champs sont obligatoires.")
                    else:
                        nouvelle_relance = {
                            "date": date_relance,
                            "prenom": prenom,
                            "commentaire": commentaire
                        }
                        if numero_facture not in relances:
                            relances[numero_facture] = []
                        relances[numero_facture].append(nouvelle_relance)

                        # Sauvegarde dans fichier JSON commun
                        try:
                            with open(fichier_relances, "w", encoding="utf-8") as f:
                                json.dump(relances, f, ensure_ascii=False, indent=2)
                            st.success("Relance ajoutée et sauvegardée !")
                        except Exception as e:
                            st.error(f"Erreur lors de la sauvegarde : {e}")

        compteur += 1

# Affichage historique uploads
if uploads:
    st.sidebar.markdown("### 📂 Historique des fichiers uploadés")
    for up in reversed(uploads[-10:]):  # afficher les 10 derniers
        st.sidebar.write(f"- {up['datetime']} : {up['filename']}")
