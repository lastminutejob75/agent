# 📸 Mapping des Images pour la Landing Page

## Images à ajouter dans `public/images/`

### 1️⃣ ComparisonSection (Avant/Après)

#### `/images/before-stressed-professional.jpg`
**Description :** Femme stressée au téléphone dans un bureau
- Professionnel débordé par les appels
- Expression stressée
- Contexte bureau/réception

#### `/images/after-organized-professional.jpg`
**Description :** Médecin souriant avec tablette UWI
- Professionnel serein avec tablette
- Écran montre interface UWI avec statistiques
- Expression satisfaite et organisée

---

### 2️⃣ SolutionsGridSection (3 solutions)

#### `/images/solution-rdv.jpg`
**Description :** Homme en costume présentant écran avec statistiques UWI
- Présentation avec écran mural
- Graphiques et statistiques UWI visibles
- Contexte professionnel/bureau

#### `/images/solution-sav.jpg`
**Description :** Homme sur canapé avec smartphone montrant confirmation RDV
- Personne détendue avec smartphone
- Écran montre message de confirmation "Votre RDV est confirmé"
- Message en bulle verte (style WhatsApp)

#### `/images/solution-questions.jpg`
**Description :** Médecin avec écran calendrier/scheduling
- Professionnel médical au bureau
- Écran montre calendrier/planning
- Contexte consultation médicale

---

### 3️⃣ WorkflowArtisanSection (3 étapes)

#### `/images/workflow-plumber-calls.jpg`
**Description :** Artisans débordés au téléphone en atelier
- Techniciens/artisans au travail
- Téléphone à l'oreille, expression stressée
- Contexte atelier/chantier avec outils

#### `/images/workflow-uwi-qualification.jpg`
**Description :** Artisan avec smartphone montrant notification UWI "Nouveau RDV"
- Technicien en tenue de travail
- Smartphone avec notification UWI
- Texte "Nouveau RDV : UWI a pris un rendez-vous client..."

#### `/images/workflow-optimized-planning.jpg`
**Description :** Réceptionniste souriante au téléphone
- Femme professionnelle souriante
- Téléphone à l'oreille, expression satisfaite
- Contexte réception/bureau bien organisé

---

### 4️⃣ Hero Section

#### `/images/hero-tablet.jpg`
**Description :** Médecin avec tablette UWI montrant interface
- Professionnel médical avec tablette
- Écran montre interface UWI avec fonctionnalités
- Expression professionnelle et confiante

---

## 📋 Dimensions recommandées

- **Hero** : 1200x800px (ratio 3:2)
- **ComparisonSection** : 1200x800px (ratio 3:2)
- **SolutionsGridSection** : 800x800px (ratio 1:1)
- **WorkflowArtisanSection** : 1000x800px (ratio 5:4)

---

## ✅ Activation des images

Une fois les images ajoutées dans `public/images/`, décommenter les balises `<img>` dans :
- `ComparisonSection.tsx` (lignes ~70 et ~100)
- `SolutionsGridSection.tsx` (ligne ~73)
- `WorkflowArtisanSection.tsx` (ligne ~52)
- `Hero.tsx` (ligne ~43)
