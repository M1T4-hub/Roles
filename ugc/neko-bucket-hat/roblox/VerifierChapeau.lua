--[[
	Neko Bucket Hat : vérification (et petites corrections) avant publication.

	Utilisation :
	  1. Génère l'Accessory avec l'Accessory Fitting Tool (onglet Avatar > Accessory).
	  2. Sélectionne cet Accessory dans l'Explorer.
	  3. Ouvre la Command Bar (View > Command Bar), colle tout ce fichier, Entrée.
	  4. Lis le rapport dans l'Output (View > Output).

	Ne corrige que ce que la spec Roblox impose (type Hat, matériau Plastic,
	transparence 0, VertexColor 1,1,1). Tout le reste est seulement signalé.
]]

local Selection = game:GetService("Selection")
local ChangeHistoryService = game:GetService("ChangeHistoryService")

-- Boîtes max pour un Hat (X, Y, Z en studs, centrées sur l'attachment).
local LIMITS = {
	Classic = Vector3.new(3, 4, 3),
	ProportionsNormal = Vector3.new(1.87, 2.5, 1.87),
	ProportionsSlender = Vector3.new(1.78, 2.5, 1.78),
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
	recording = ChangeHistoryService:TryBeginRecording("Vérifier NekoBucketHat")
end)

-- 1. Type d'accessoire
if accessory.AccessoryType == Enum.AccessoryType.Hat then
	pass("AccessoryType = Hat")
else
	accessory.AccessoryType = Enum.AccessoryType.Hat
	fixed("AccessoryType réglé sur Hat")
end

-- 2. Handle
local handle = accessory:FindFirstChild("Handle")
if not (handle and handle:IsA("MeshPart")) then
	fail("Il faut un MeshPart nommé « Handle » directement dans l'Accessory.")
else
	pass("Handle MeshPart présent")

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
		fail("Pas de texture : mets l'ID de NekoBucketHat_<Couleur>_Albedo.png dans Handle.TextureID.")
	end

	-- 3. Attachment
	local attachment = handle:FindFirstChild("HatAttachment")
	if attachment and attachment:IsA("Attachment") then
		pass("HatAttachment présent")

		-- 4. Taille, mesurée dans le repère de l'attachment comme le fait Roblox
		local scaleValue = handle:FindFirstChild("AvatarPartScaleType")
		local scaleType = scaleValue and scaleValue:IsA("StringValue") and scaleValue.Value or "Classic"
		local limit = LIMITS[scaleType] or LIMITS.Classic
		local half = handle.Size / 2
		local ext = Vector3.zero
		for _, sx in ipairs({ -1, 1 }) do
			for _, sy in ipairs({ -1, 1 }) do
				for _, sz in ipairs({ -1, 1 }) do
					local p = attachment.CFrame:PointToObjectSpace(half * Vector3.new(sx, sy, sz))
					ext = ext:Max(Vector3.new(math.abs(p.X), math.abs(p.Y), math.abs(p.Z)))
				end
			end
		end
		local need = ext * 2
		local text = ("%.2f × %.2f × %.2f (max %.2f × %.2f × %.2f, échelle %s)"):format(
			need.X, need.Y, need.Z, limit.X, limit.Y, limit.Z, scaleType)
		if need.X <= limit.X and need.Y <= limit.Y and need.Z <= limit.Z then
			pass("Taille OK : " .. text)
		else
			fail("Trop grand : " .. text .. " → réduis l'échelle dans l'Accessory Fitting Tool.")
		end
	else
		fail("HatAttachment manquant dans le Handle (régénère avec l'Accessory Fitting Tool, type Hat).")
	end
end

-- 5. Rien d'autre dans l'Accessory (pas de scripts ni de parts en trop)
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
	print("🎉 Prêt : clic droit sur l'Accessory > Save to Roblox > Avatar Asset > Hat.")
end
