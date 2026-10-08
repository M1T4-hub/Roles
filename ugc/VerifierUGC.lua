--[[
	Vérification (et petites corrections) d'un accessoire UGC avant publication.
	Fonctionne pour tous les accessoires rigides : Hat, Hair, Face, Neck,
	Shoulder, Front, Back, Waist.

	Utilisation :
	  1. Génère l'Accessory avec l'Accessory Fitting Tool (onglet Avatar > Accessory).
	  2. Sélectionne cet Accessory dans l'Explorer.
	  3. Ouvre la Command Bar (View > Command Bar), colle tout ce fichier, Entrée.
	  4. Lis le rapport dans l'Output (View > Output).

	Corrige seulement ce que la spec Roblox impose (matériau Plastic,
	transparence 0, VertexColor 1,1,1). Tout le reste est signalé.
]]

local Selection = game:GetService("Selection")
local ChangeHistoryService = game:GetService("ChangeHistoryService")

-- Boîtes max en studs, dans le repère de l'attachment (-Z = devant l'avatar).
-- { {xmin, xmax}, {ymin, ymax}, {zmin, zmax} }
local function centred(w, h, d)
	return { { -w / 2, w / 2 }, { -h / 2, h / 2 }, { -d / 2, d / 2 } }
end
local LIMITS = {
	Hat = { Classic = centred(3, 4, 3), ProportionsNormal = centred(1.87, 2.5, 1.87),
		ProportionsSlender = centred(1.78, 2.5, 1.78) },
	Hair = { Classic = { { -1.5, 1.5 }, { -3, 2 }, { -1.5, 2 } },
		ProportionsNormal = { { -0.935, 0.935 }, { -1.875, 1.25 }, { -0.9375, 1.25 } },
		ProportionsSlender = { { -0.89, 0.89 }, { -1.875, 1.25 }, { -0.892, 1.189 } } },
	Face = { Classic = centred(3, 2, 2), ProportionsNormal = centred(1.87, 1.25, 1.25),
		ProportionsSlender = centred(1.78, 1.25, 1.18) },
	Neck = { Classic = centred(3, 3, 2), ProportionsNormal = centred(2.95, 3.68, 2.16),
		ProportionsSlender = centred(2.59, 3.39, 1.92) },
	ShoulderNeck = { Classic = centred(7, 3, 3), ProportionsNormal = centred(6.9, 3.68, 3.24),
		ProportionsSlender = centred(6.05, 3.39, 2.88) },
	ShoulderCollar = { Classic = centred(3, 3, 3), ProportionsNormal = centred(2.95, 3.68, 3.24),
		ProportionsSlender = centred(2.59, 3.39, 2.88) },
	ShoulderArm = { Classic = centred(3, 3, 3), ProportionsNormal = centred(2.67, 4.4, 3.09),
		ProportionsSlender = centred(2.37, 3.96, 2.75) },
	Front = { Classic = centred(3, 3, 3), ProportionsNormal = centred(2.95, 3.68, 3.24),
		ProportionsSlender = centred(2.59, 3.39, 2.88) },
	Back = { Classic = { { -5, 5 }, { -3.5, 3.5 }, { -1.5, 3 } },
		ProportionsNormal = { { -4.93, 4.93 }, { -4.295, 4.295 }, { -1.623, 3.246 } },
		ProportionsSlender = { { -4.32, 4.32 }, { -3.955, 3.955 }, { -1.443, 2.886 } } },
	Waist = { Classic = { { -2, 2 }, { -2, 1.5 }, { -3.5, 3.5 } },
		ProportionsNormal = { { -1.97, 1.97 }, { -2.457, 1.842 }, { -3.785, 3.785 } },
		ProportionsSlender = { { -1.88, 1.88 }, { -1.885, 1.414 }, { -3.365, 3.365 } } },
}

-- Nom d'attachment -> (AccessoryType attendu, clé de LIMITS)
local ATTACHMENTS = {
	HatAttachment = { "Hat", "Hat" },
	HairAttachment = { "Hair", "Hair" },
	FaceFrontAttachment = { "Face", "Face" },
	FaceCenterAttachment = { "Face", "Face" },
	NeckAttachment = { "Neck", "Neck" },
	RightCollarAttachment = { "Shoulder", "ShoulderCollar" },
	LeftCollarAttachment = { "Shoulder", "ShoulderCollar" },
	RightShoulderAttachment = { "Shoulder", "ShoulderArm" },
	LeftShoulderAttachment = { "Shoulder", "ShoulderArm" },
	BodyFrontAttachment = { "Front", "Front" },
	BodyBackAttachment = { "Back", "Back" },
	WaistFrontAttachment = { "Waist", "Waist" },
	WaistCenterAttachment = { "Waist", "Waist" },
	WaistBackAttachment = { "Waist", "Waist" },
}

local ok_count, fix_count, err_count = 0, 0, 0
local function pass(msg)
	ok_count += 1
	print("✅ " .. msg)
end
local function fixed(msg)
	fix_count += 1
	print("🔧 " .. msg)
end
local function fail(msg)
	err_count += 1
	warn("❌ " .. msg)
end

-- Trouve l'Accessory : la sélection, son ancêtre, ou le premier du Workspace.
local accessory = Selection:Get()[1]
if accessory and not accessory:IsA("Accessory") then
	accessory = accessory:FindFirstAncestorWhichIsA("Accessory")
end
if not accessory then
	accessory = workspace:FindFirstChildWhichIsA("Accessory", true)
end
if not accessory then
	warn("❌ Aucun Accessory trouvé. Génère-le d'abord avec l'Accessory Fitting Tool.")
	return
end
print(("—— Vérification de « %s » ——"):format(accessory:GetFullName()))

local recording
pcall(function()
	recording = ChangeHistoryService:TryBeginRecording("Vérifier accessoire UGC")
end)

local handle = accessory:FindFirstChild("Handle")
if not (handle and handle:IsA("MeshPart")) then
	fail("Il faut un MeshPart nommé « Handle » directement dans l'Accessory.")
else
	pass("Handle MeshPart présent")

	-- Attachment et type
	local attachment, info
	for _, child in ipairs(handle:GetChildren()) do
		if child:IsA("Attachment") and ATTACHMENTS[child.Name] then
			attachment, info = child, ATTACHMENTS[child.Name]
			break
		end
	end
	if not attachment then
		fail("Aucun attachment reconnu dans le Handle (régénère avec l'Accessory Fitting Tool).")
	else
		pass(("Attachment %s"):format(attachment.Name))
		local expected = info[1]
		local current = accessory.AccessoryType.Name
		if current == expected then
			pass("AccessoryType = " .. current)
		elseif current == "Unknown" then
			accessory.AccessoryType = Enum.AccessoryType[expected]
			fixed("AccessoryType réglé sur " .. expected)
		else
			fail(("AccessoryType = %s mais l'attachment %s correspond à %s."):format(
				current, attachment.Name, expected))
		end

		-- Taille, mesurée dans le repère de l'attachment comme le fait Roblox
		local scaleValue = handle:FindFirstChild("AvatarPartScaleType")
		local scaleType = scaleValue and scaleValue:IsA("StringValue") and scaleValue.Value or "Classic"
		local box = LIMITS[info[2]][scaleType] or LIMITS[info[2]].Classic
		local half = handle.Size / 2
		local lo = Vector3.new(math.huge, math.huge, math.huge)
		local hi = -lo
		for _, sx in ipairs({ -1, 1 }) do
			for _, sy in ipairs({ -1, 1 }) do
				for _, sz in ipairs({ -1, 1 }) do
					local p = attachment.CFrame:PointToObjectSpace(half * Vector3.new(sx, sy, sz))
					lo = lo:Min(p)
					hi = hi:Max(p)
				end
			end
		end
		local inside = lo.X >= box[1][1] and hi.X <= box[1][2]
			and lo.Y >= box[2][1] and hi.Y <= box[2][2]
			and lo.Z >= box[3][1] and hi.Z <= box[3][2]
		local text = ("X %.2f..%.2f  Y %.2f..%.2f  Z %.2f..%.2f (échelle %s)"):format(
			lo.X, hi.X, lo.Y, hi.Y, lo.Z, hi.Z, scaleType)
		if inside then
			pass("Taille OK : " .. text)
		else
			fail(("Hors limites : %s, max X %.2f..%.2f  Y %.2f..%.2f  Z %.2f..%.2f → réduis l'échelle dans l'Accessory Fitting Tool."):format(
				text, box[1][1], box[1][2], box[2][1], box[2][2], box[3][1], box[3][2]))
		end
	end

	if handle.Material == Enum.Material.Plastic then
		pass("Material = Plastic")
	else
		handle.Material = Enum.Material.Plastic
		fixed("Material réglé sur Plastic")
	end

	if handle.Transparency == 0 then
		pass("Transparency = 0")
	else
		handle.Transparency = 0
		fixed("Transparency réglée sur 0")
	end

	local hasVertexColor, vertexColor = pcall(function()
		return handle.VertexColor
	end)
	if hasVertexColor and typeof(vertexColor) == "Vector3" then
		if vertexColor == Vector3.one then
			pass("VertexColor = 1, 1, 1")
		else
			handle.VertexColor = Vector3.one
			fixed("VertexColor remis à 1, 1, 1")
		end
	end

	local surface = handle:FindFirstChildWhichIsA("SurfaceAppearance")
	if handle.TextureID ~= "" or (surface and surface.ColorMap ~= "") then
		pass("Texture appliquée")
	else
		fail("Pas de texture : importe le PNG <Nom>_<Couleur>_Albedo.png et mets son ID dans Handle.TextureID.")
	end
end

-- Rien d'autre dans l'Accessory (pas de scripts ni de parts en trop)
local extras = {}
for _, d in ipairs(accessory:GetDescendants()) do
	if d:IsA("LuaSourceContainer") or (d:IsA("BasePart") and d ~= handle) then
		table.insert(extras, d:GetFullName())
	end
end
if #extras == 0 then
	pass("Aucun objet en trop (scripts / parts)")
else
	fail("Objets à supprimer avant l'upload : " .. table.concat(extras, ", "))
end

if recording then
	ChangeHistoryService:FinishRecording(recording, Enum.FinishRecordingOperation.Commit)
end

print(("—— %d OK, %d corrigé(s), %d erreur(s) ——"):format(ok_count, fix_count, err_count))
if err_count == 0 then
	print(("🎉 Prêt : clic droit sur l'Accessory > Save to Roblox > Avatar Asset > %s."):format(
		accessory.AccessoryType.Name))
end
