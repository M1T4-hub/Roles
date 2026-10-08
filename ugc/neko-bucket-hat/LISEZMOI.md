# Bob Oreilles de Chat Kawaii + Nœud : UGC Roblox (Hat)

Un bob trop mignon avec oreilles de chat, nœud coquette à perle et petite patte. Style plastique simple et propre. Existe en 5 couleurs : Rose, Matcha, Minuit, Nuage et Choco !

![Les 5 coloris](previews/coloris.png)

## Fichiers

| Coloris | À importer dans Studio | Texture seule (dépannage) |
|---|---|---|
| Fraise | [`fbx/NekoBucketHat_Fraise.fbx`](fbx/NekoBucketHat_Fraise.fbx) | `textures/NekoBucketHat_Fraise_Albedo.png` |
| Matcha | [`fbx/NekoBucketHat_Matcha.fbx`](fbx/NekoBucketHat_Matcha.fbx) | `textures/NekoBucketHat_Matcha_Albedo.png` |
| Minuit | [`fbx/NekoBucketHat_Minuit.fbx`](fbx/NekoBucketHat_Minuit.fbx) | `textures/NekoBucketHat_Minuit_Albedo.png` |
| Nuage | [`fbx/NekoBucketHat_Nuage.fbx`](fbx/NekoBucketHat_Nuage.fbx) | `textures/NekoBucketHat_Nuage_Albedo.png` |
| Choco | [`fbx/NekoBucketHat_Choco.fbx`](fbx/NekoBucketHat_Choco.fbx) | `textures/NekoBucketHat_Choco_Albedo.png` |

Chaque `.fbx` contient le maillage **et** sa texture.

## Dans Roblox Studio

1. **Import 3D** : choisis un des `.fbx` ci-dessus et ne change aucun réglage (*Scale Unit* = Studs, *World Forward* = Front, *World Up* = Top). Taille affichée : environ **1,74 × 0,99 × 1,74** studs, **3 820 triangles**.
2. **Avatar › Accessory** (Accessory Fitting Tool) : *Part* = le MeshPart `NekoBucketHat`, *Asset Type* = **Accessory › Hat**, *body type* = **Classic**.
3. **Placement** : Le bob se pose bien droit sur la tête, le bord juste au-dessus des yeux ; la patte est devant et le nœud sur le côté avant droit.
4. **Generate MeshPart Accessory**, puis sélectionne l'Accessory et colle [`VerifierUGC.lua`](../VerifierUGC.lua) dans la Command Bar : il doit afficher « 🎉 Prêt ».
5. Clic droit sur l'Accessory › **Save to Roblox** › *Avatar Asset* › **Hat**.

## Fiche Marketplace

| Coloris | Titre EN | Titre FR |
|---|---|---|
| Fraise | `Kawaii Cat Ear Bucket Hat w/ Bow - Pink` | `Bob Oreilles de Chat Kawaii + Nœud - Fraise` |
| Matcha | `Kawaii Cat Ear Bucket Hat w/ Bow - Matcha` | `Bob Oreilles de Chat Kawaii + Nœud - Matcha` |
| Minuit | `Kawaii Cat Ear Bucket Hat w/ Bow - Midnight` | `Bob Oreilles de Chat Kawaii + Nœud - Minuit` |
| Nuage | `Kawaii Cat Ear Bucket Hat w/ Bow - Cloud` | `Bob Oreilles de Chat Kawaii + Nœud - Nuage` |
| Choco | `Kawaii Cat Ear Bucket Hat w/ Bow - Cocoa` | `Bob Oreilles de Chat Kawaii + Nœud - Choco` |

**Description (EN)**
```
A cute bucket hat with cat ears, a coquette bow with a pearl and a little paw print. Clean, simple plastic style. Available in 5 colors: Pink, Matcha, Midnight, Cloud and Cocoa!
```
**Description (FR)**
```
Un bob trop mignon avec oreilles de chat, nœud coquette à perle et petite patte. Style plastique simple et propre. Existe en 5 couleurs : Rose, Matcha, Minuit, Nuage et Choco !
```

## Conformité (mesurée par `tools/validate_ugc.py`)

| Règle Roblox | Limite | Cet objet |
|---|---|---|
| Triangles | ≤ 4 000 | **3820** |
| Maillage / matériau | 1 / 1 | ✅ |
| Volumes fermés, normales vers l'extérieur | tous | ✅ 9 pièces |
| Boîte Hat Classic | 3,00 × 4,00 × 3,00 | ✅ 1,74 × 0,99 × 1,74 |
| Boîte Hat Normal | 1,87 × 2,50 × 1,87 | ✅ 1,74 × 0,99 × 1,74 |
| Boîte Hat Slender | 1,78 × 2,50 × 1,78 | ✅ 1,74 × 0,99 × 1,74 |
| Texture | ≤ 1024 px | ✅ 1024 × 1024 PNG |
