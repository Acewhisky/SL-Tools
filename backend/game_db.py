"""内置游戏存档路径规则库。

参考 Ludusavi（mtkennerly/ludusavi）的开源游戏库元数据结构，
整理出主流 PC 游戏的常见存档路径。路径中使用 %XXX% 占位符，
展开规则见 utils.expand_env_path。

数据为内置精选（断网可用），同时支持用户在前端手动添加自定义游戏与路径。
"""

# 每条规则: 游戏名 -> {platform, paths, processes}
# platform: Steam / Epic / GOG / Xbox / Other（可多个）
# paths:    存档路径模板（存在即视为该游戏有存档/已安装）
# processes: 进程名列表，用于运行状态检测
GAME_RULES = {
    # ============ 用户机器上已发现的游戏 ============
    "艾尔登法环 (Elden Ring)": {
        "platform": ["Steam"],
        "paths": ["%APPDATA%/EldenRing", "%USERPROFILE%/AppData/Roaming/EldenRing"],
        "processes": ["eldenring.exe", "start_protected_game.exe"],
    },
    "博德之门3 (Baldur's Gate 3)": {
        "platform": ["Steam", "GOG"],
        "paths": ["%LOCALAPPDATA%/Larian Studios/Baldur's Gate 3", "%USERPROFILE%/AppData/Local/Larian Studios/Baldur's Gate 3/PlayerProfiles"],
        "processes": ["bg3.exe", "bg3_dx11.exe"],
    },
    "无主之地4 (Borderlands 4)": {
        "platform": ["Epic", "Steam"],
        "paths": ["%LOCALAPPDATA%/borderlands4r/Saved/SaveGames", "%USERPROFILE%/AppData/Local/borderlands4r"],
        "processes": ["borderlands4r.exe"],
    },
    "死亡搁浅2 (Death Stranding 2)": {
        "platform": ["Steam"],
        "paths": ["%LOCALAPPDATA%/DEATH STRANDING 2 - ON THE BEACH/Saved/SaveGames", "%USERPROFILE%/AppData/Local/KOJIMA PRODUCTIONS"],
        "processes": ["DeathStranding2.exe"],
    },
    "死亡搁浅 (Death Stranding)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%LOCALAPPDATA%/KojimaProductions/DeathStranding", "%USERPROFILE%/AppData/Local/KojimaProductions/DeathStranding"],
        "processes": ["ds.exe"],
    },
    "终焉之莉莉 (Ender Lilies)": {
        "platform": ["Steam"],
        "paths": ["%LOCALAPPDATA%/EnderLilies", "%USERPROFILE%/AppData/Local/EnderLilies/Saved"],
        "processes": ["EnderLilies.exe"],
    },
    "无人深空 (No Man's Sky)": {
        "platform": ["Steam", "GOG", "Xbox"],
        "paths": ["%APPDATA%/HelloGames/Saves", "%USERPROFILE%/AppData/Roaming/HelloGames/Saves", "%SAVED_GAMES%/HelloGames"],
        "processes": ["NMS.exe"],
    },
    "奥日与黑暗森林 (Ori and the Blind Forest)": {
        "platform": ["Steam"],
        "paths": ["%LOCALAPPDATA%/Ori and the Blind Forest", "%USERPROFILE%/AppData/Local/Ori and the Blind Forest"],
        "processes": ["OriAndTheBlindForest.exe"],
    },
    "巫师3 (The Witcher 3)": {
        "platform": ["Steam", "GOG"],
        "paths": ["%DOCUMENTS%/The Witcher 3/gamesaves", "%USERPROFILE%/Documents/The Witcher 3/gamesaves", "%SAVED_GAMES%/CD Projekt Red/The Witcher 3"],
        "processes": ["witcher3.exe"],
    },
    "赛博朋克2077 (Cyberpunk 2077)": {
        "platform": ["Steam", "GOG", "Epic"],
        "paths": ["%USERPROFILE%/Saved Games/CD Projekt Red/Cyberpunk 2077", "%SAVED_GAMES%/CD Projekt Red/Cyberpunk 2077"],
        "processes": ["Cyberpunk2077.exe"],
    },
    "哈迪斯2 (Hades II)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%LOCALAPPDATA%/Hades II", "%USERPROFILE%/AppData/Local/Hades II", "%SAVED_GAMES%/Hades II"],
        "processes": ["Hades2.exe"],
    },
    "天国拯救2 (Kingdom Come: Deliverance II)": {
        "platform": ["Steam"],
        "paths": ["%SAVED_GAMES%/kingdomcome2/saves", "%USERPROFILE%/Saved Games/kingdomcome2"],
        "processes": ["KingdomCome.exe"],
    },
    "星刃 (Stellar Blade)": {
        "platform": ["Steam"],
        "paths": ["%DOCUMENTS%/StellarBlade/Saved/SaveGames", "%USERPROFILE%/Documents/StellarBlade"],
        "processes": ["StellarBlade.exe"],
    },
    "僵尸毁灭工程 (Project Zomboid)": {
        "platform": ["Steam", "GOG"],
        "paths": ["%USERPROFILE%/Zomboid/Saves", "%USERPROFILE%/Zomboid"],
        "processes": ["ProjectZomboid64.exe"],
    },
    "神之天平 (ASTLIBRA)": {
        "platform": ["Steam"],
        "paths": ["%LOCALAPPDATA%/ASTLIBRA", "%USERPROFILE%/AppData/Local/ASTLIBRA"],
        "processes": ["ASTLIBRA.exe"],
    },
    "战锤40K：暗潮 (Darktide)": {
        "platform": ["Steam"],
        "paths": ["%APPDATA%/Fatshark/Darktide", "%USERPROFILE%/AppData/Roaming/Fatshark/Darktide"],
        "processes": ["darktide.exe"],
    },
    "战锤：末世鼠疫2 (Vermintide 2)": {
        "platform": ["Steam"],
        "paths": ["%APPDATA%/Fatshark/Vermintide2", "%USERPROFILE%/AppData/Roaming/Fatshark/Vermintide2"],
        "processes": ["vermintide2.exe"],
    },
    "艾尔登法环：黑夜君临": {
        "platform": ["Steam"],
        "paths": ["%APPDATA%/EldenRing Nightreign", "%USERPROFILE%/AppData/Roaming/EldenRing Nightreign"],
        "processes": ["EldenRingNightreign.exe"],
    },
    "八方旅人2 (Octopath Traveler II)": {
        "platform": ["Steam"],
        "paths": ["%DOCUMENTS%/My Games/Octopath_Traveler_II", "%USERPROFILE%/Documents/My Games/Octopath_Traveler_II"],
        "processes": ["Octopath_Traveler_II.exe"],
    },
    "勇者斗恶龙11S": {
        "platform": ["Steam"],
        "paths": ["%DOCUMENTS%/My Games/Dragon Quest XI S", "%USERPROFILE%/Documents/My Games/Dragon Quest XI S"],
        "processes": ["DragonQuestXI.exe"],
    },
    "最终幻想7 重生 (FF7 Rebirth)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%DOCUMENTS%/My Games/FINAL FANTASY VII REBIRTH/Saved", "%USERPROFILE%/Documents/My Games/FINAL FANTASY VII REBIRTH"],
        "processes": ["ff7rebirth_.exe"],
    },
    "最终幻想7 重制版 (FF7 Remake)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%DOCUMENTS%/My Games/FINAL FANTASY VII REMAKE/Saved", "%USERPROFILE%/Documents/My Games/FINAL FANTASY VII REMAKE"],
        "processes": ["ff7remake_.exe"],
    },
    "最终幻想16 (FF16)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%DOCUMENTS%/My Games/FINAL FANTASY XVI", "%USERPROFILE%/Documents/My Games/FINAL FANTASY XVI"],
        "processes": ["FFXVI.exe"],
    },
    "最终幻想14 (FF14)": {
        "platform": ["Steam"],
        "paths": ["%DOCUMENTS%/My Games/FINAL FANTASY XIV - A Realm Reborn", "%USERPROFILE%/Documents/My Games/FINAL FANTASY XIV - A Realm Reborn"],
        "processes": ["ffxiv_dx11.exe"],
    },
    "尼尔：机械纪元 (Nier Automata)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%DOCUMENTS%/My Games/NieR_Automata", "%USERPROFILE%/Documents/My Games/NieR_Automata"],
        "processes": ["NieRAutomata.exe"],
    },
    "生化危机4重制版 (RE4 Remake)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%LOCALAPPDATA%/RE4", "%USERPROFILE%/AppData/Local/RE4"],
        "processes": ["re4.exe"],
    },
    "生化危机8 (Resident Evil Village)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%LOCALAPPDATA%/RESIDENT EVIL VILLAGE", "%USERPROFILE%/AppData/Local/RESIDENT EVIL VILLAGE"],
        "processes": ["re8.exe"],
    },
    "怪物猎人：荒野 (Monster Hunter Wilds)": {
        "platform": ["Steam"],
        "paths": ["%LOCALAPPDATA%/MonsterHunterWilds", "%USERPROFILE%/AppData/Local/MonsterHunterWilds"],
        "processes": ["MonsterHunterWilds.exe"],
    },
    "怪物猎人：世界 (MH World)": {
        "platform": ["Steam"],
        "paths": ["%LOCALAPPDATA%/MonsterHunterWorld", "%USERPROFILE%/AppData/Local/MonsterHunterWorld/Saved/SaveGames"],
        "processes": ["MonsterHunterWorld.exe"],
    },
    "怪物猎人：崛起 (MH Rise)": {
        "platform": ["Steam"],
        "paths": ["%LOCALAPPDATA%/MH_Rise", "%USERPROFILE%/AppData/Local/MH_Rise"],
        "processes": ["MonsterHunterRise.exe"],
    },
    "黑暗之魂3 (Dark Souls III)": {
        "platform": ["Steam"],
        "paths": ["%APPDATA%/DarkSoulsIII", "%USERPROFILE%/AppData/Roaming/DarkSoulsIII"],
        "processes": ["DarkSoulsIII.exe"],
    },
    "只狼 (Sekiro)": {
        "platform": ["Steam"],
        "paths": ["%APPDATA%/Sekiro", "%USERPROFILE%/AppData/Roaming/Sekiro"],
        "processes": ["sekiro.exe"],
    },
    "对马岛之魂 (Ghost of Tsushima)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%DOCUMENTS%/Ghost of Tsushima DIRECTOR'S CUT", "%USERPROFILE%/Documents/Ghost of Tsushima DIRECTOR'S CUT"],
        "processes": ["GhostOfTsushima.exe"],
    },
    "战神 (God of War)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%DOCUMENTS%/God of War", "%USERPROFILE%/Documents/God of War"],
        "processes": ["GoW.exe"],
    },
    "战神：诸神黄昏 (God of War Ragnarok)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%DOCUMENTS%/God of War Ragnarök", "%USERPROFILE%/Documents/God of War Ragnarök"],
        "processes": ["GoWRagnarok.exe"],
    },
    "地平线：零之曙光 (Horizon Zero Dawn)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%DOCUMENTS%/Horizon Zero Dawn", "%USERPROFILE%/Documents/Horizon Zero Dawn"],
        "processes": ["HorizonZeroDawn.exe"],
    },
    "地平线：西之绝境 (Horizon Forbidden West)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%DOCUMENTS%/Horizon Forbidden West", "%USERPROFILE%/Documents/Horizon Forbidden West"],
        "processes": ["HorizonForbiddenWest.exe"],
    },
    "漫威蜘蛛侠 (Marvel's Spider-Man)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%APPDATA%/Marvel's Spider-Man", "%USERPROFILE%/AppData/Roaming/Marvel's Spider-Man"],
        "processes": ["Spider-Man.exe"],
    },
    "荒野大镖客2 (Red Dead Redemption 2)": {
        "platform": ["Steam", "Epic", "Rockstar"],
        "paths": ["%DOCUMENTS%/Rockstar Games/Red Dead Redemption 2/Profiles", "%USERPROFILE%/Documents/Rockstar Games/Red Dead Redemption 2"],
        "processes": ["RDR2.exe"],
    },
    "GTA5 (Grand Theft Auto V)": {
        "platform": ["Steam", "Epic", "Rockstar"],
        "paths": ["%DOCUMENTS%/Rockstar Games/GTA V/Profiles", "%USERPROFILE%/Documents/Rockstar Games/GTA V"],
        "processes": ["GTA5.exe"],
    },
    "赛博朋克2077之外" : None,  # 占位避免歧义，将被忽略
    "泰坦陨落2 (Titanfall 2)": {
        "platform": ["Steam", "Origin"],
        "paths": ["%DOCUMENTS%/Respawn/Titanfall2", "%USERPROFILE%/Documents/Respawn/Titanfall2"],
        "processes": ["Titanfall2.exe"],
    },
    "Apex英雄 (Apex Legends)": {
        "platform": ["Steam", "EA"],
        "paths": ["%SAVED_GAMES%/Respawn/Apex", "%USERPROFILE%/Saved Games/Respawn/Apex"],
        "processes": ["r5apex.exe"],
    },
    "双人成行 (It Takes Two)": {
        "platform": ["Steam", "EA"],
        "paths": ["%LOCALAPPDATA%/It Takes Two", "%USERPROFILE%/AppData/Local/It Takes Two"],
        "processes": ["ItTakesTwo.exe"],
    },
    "逃出生天 (A Way Out)": {
        "platform": ["Steam", "EA"],
        "paths": ["%LOCALAPPDATA%/A Way Out", "%USERPROFILE%/AppData/Local/A Way Out"],
        "processes": ["AWayOut.exe"],
    },
    "星空 (Starfield)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%DOCUMENTS%/My Games/Starfield/Saves", "%USERPROFILE%/Documents/My Games/Starfield"],
        "processes": ["Starfield.exe"],
    },
    "上古卷轴5 (Skyrim SE)": {
        "platform": ["Steam"],
        "paths": ["%DOCUMENTS%/My Games/Skyrim Special Edition/Saves", "%USERPROFILE%/Documents/My Games/Skyrim Special Edition"],
        "processes": ["SkyrimSE.exe"],
    },
    "辐射4 (Fallout 4)": {
        "platform": ["Steam", "GOG"],
        "paths": ["%DOCUMENTS%/My Games/Fallout4/Saves", "%USERPROFILE%/Documents/My Games/Fallout4"],
        "processes": ["Fallout4.exe"],
    },
    "消逝的光芒2 (Dying Light 2)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%USERPROFILE%/Saved Games/dying light 2", "%SAVED_GAMES%/dying light 2"],
        "processes": ["DyingLightGame.exe"],
    },
    "消逝的光芒 (Dying Light)": {
        "platform": ["Steam", "GOG"],
        "paths": ["%DOCUMENTS%/DyingLight", "%USERPROFILE%/Documents/DyingLight"],
        "processes": ["DyingLightGame.exe"],
    },
    "霍格沃茨之遗 (Hogwarts Legacy)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%LOCALAPPDATA%/Hogwarts Legacy/Saved/SaveGames", "%USERPROFILE%/AppData/Local/Hogwarts Legacy"],
        "processes": ["HogwartsLegacy.exe"],
    },
    "荒野之息模拟/王国之泪 (Zelda)": {
        "platform": ["Other"],
        "paths": [],
        "processes": [],
    },
    "星露谷物语 (Stardew Valley)": {
        "platform": ["Steam", "GOG", "Xbox"],
        "paths": ["%APPDATA%/StardewValley/Saves", "%USERPROFILE%/AppData/Roaming/StardewValley/Saves"],
        "processes": ["Stardew Valley.exe"],
    },
    "泰拉瑞亚 (Terraria)": {
        "platform": ["Steam", "GOG"],
        "paths": ["%DOCUMENTS%/My Games/Terraria", "%USERPROFILE%/Documents/My Games/Terraria"],
        "processes": ["Terraria.exe"],
    },
    "我的世界 (Minecraft Java)": {
        "platform": ["Other"],
        "paths": ["%APPDATA%/.minecraft/saves", "%USERPROFILE%/AppData/Roaming/.minecraft/saves"],
        "processes": ["javaw.exe"],
    },
    "我的世界基岩版 (Minecraft Bedrock)": {
        "platform": ["Xbox", "Other"],
        "paths": ["%LOCALAPPDATA%/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/games/com.mojang/minecraftWorlds", "%USERPROFILE%/AppData/Local/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/games/com.mojang/minecraftWorlds"],
        "processes": ["Minecraft.Windows.exe"],
    },
    "空洞骑士 (Hollow Knight)": {
        "platform": ["Steam", "GOG"],
        "paths": ["%USERPROFILE%/AppData/LocalLow/Team Cherry/Hollow Knight", "%LOCALAPPDATA%/../LocalLow/Team Cherry/Hollow Knight"],
        "processes": ["hollow_knight.exe"],
    },
    "蔚蓝 (Celeste)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%USERPROFILE%/AppData/Roaming/Celeste", "%APPDATA%/Celeste"],
        "processes": ["Celeste.exe"],
    },
    "死亡细胞 (Dead Cells)": {
        "platform": ["Steam", "GOG", "Xbox"],
        "paths": ["%LOCALAPPDATA%/DeadCells", "%USERPROFILE%/AppData/Local/DeadCells"],
        "processes": ["deadcells.exe"],
    },
    "哈迪斯 (Hades)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%LOCALAPPDATA%/Hades", "%USERPROFILE%/AppData/Local/Hades"],
        "processes": ["Hades.exe"],
    },
    "吸血鬼幸存者 (Vampire Survivors)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%APPDATA%/Vampire_Survivors", "%USERPROFILE%/AppData/Roaming/Vampire_Survivors"],
        "processes": ["Vampire Survivors.exe"],
    },
    "杀戮尖塔 (Slay the Spire)": {
        "platform": ["Steam", "GOG"],
        "paths": ["%LOCALAPPDATA%/SlayTheSpire", "%USERPROFILE%/AppData/Local/SlayTheSpire"],
        "processes": ["SlayTheSpire.exe"],
    },
    "遗迹2 (Remnant II)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%USERPROFILE%/Saved Games/Remnant2", "%SAVED_GAMES%/Remnant2"],
        "processes": ["Remnant2.exe"],
    },
    "仁王2 (Nioh 2)": {
        "platform": ["Steam"],
        "paths": ["%DOCUMENTS%/KoeiTecmo/NIOH2", "%USERPROFILE%/Documents/KoeiTecmo/NIOH2"],
        "processes": ["nioh2.exe"],
    },
    "浪人崛起 (Rise of the Ronin)": {
        "platform": ["Steam"],
        "paths": ["%DOCUMENTS%/KoeiTecmo/RONIN", "%USERPROFILE%/Documents/KoeiTecmo/RONIN"],
        "processes": ["RONIN.exe"],
    },
    "卧龙：苍天陨落 (Wo Long)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%DOCUMENTS%/KoeiTecmo/WO LONG", "%USERPROFILE%/Documents/KoeiTecmo/WO LONG"],
        "processes": ["WoLong.exe"],
    },
    "匹诺曹的谎言 (Lies of P)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%LOCALAPPDATA%/LiesOfP/Saved/SaveGames", "%USERPROFILE%/AppData/Local/LiesOfP"],
        "processes": ["LiesOfP.exe"],
    },
    "暗黑破坏神4 (Diablo IV)": {
        "platform": ["Battle.net"],
        "paths": ["%DOCUMENTS%/Diablo IV", "%USERPROFILE%/Documents/Diablo IV"],
        "processes": ["Diablo IV.exe"],
    },
    "暗黑破坏神2重制版 (D2R)": {
        "platform": ["Battle.net"],
        "paths": ["%DOCUMENTS%/Diablo II Resurrected", "%USERPROFILE%/Documents/Diablo II Resurrected"],
        "processes": ["D2R.exe"],
    },
    "暗黑破坏神3 (Diablo III)": {
        "platform": ["Battle.net"],
        "paths": ["%DOCUMENTS%/Diablo III", "%USERPROFILE%/Documents/Diablo III"],
        "processes": ["Diablo III64.exe"],
    },
    "魔兽世界 (World of Warcraft)": {
        "platform": ["Battle.net"],
        "paths": ["%DOCUMENTS%/World of Warcraft", "%USERPROFILE%/Documents/World of Warcraft"],
        "processes": ["Wow.exe"],
    },
    "守望先锋2 (Overwatch 2)": {
        "platform": ["Battle.net"],
        "paths": ["%DOCUMENTS%/Overwatch", "%USERPROFILE%/Documents/Overwatch"],
        "processes": ["Overwatch.exe"],
    },
    "原神 (Genshin Impact)": {
        "platform": ["Other"],
        "paths": ["%USERPROFILE%/AppData/Local/miHoYo/Genshin Impact", "%LOCALAPPDATA%/miHoYo/Genshin Impact"],
        "processes": ["GenshinImpact.exe"],
    },
    "崩坏：星穹铁道 (Honkai Star Rail)": {
        "platform": ["Other"],
        "paths": ["%USERPROFILE%/AppData/Local/miHoYo/崩坏：星穹铁道", "%LOCALAPPDATA%/miHoYo/崩坏：星穹铁道"],
        "processes": ["StarRail.exe"],
    },
    "绝区零 (Zenless Zone Zero)": {
        "platform": ["Other"],
        "paths": ["%USERPROFILE%/AppData/Local/miHoYo/绝区零", "%LOCALAPPDATA%/miHoYo/绝区零"],
        "processes": ["ZenlessZoneZero.exe"],
    },
    "鸣潮 (Wuthering Waves)": {
        "platform": ["Other"],
        "paths": ["%LOCALAPPDATA%/WutheringWaves", "%USERPROFILE%/AppData/Local/WutheringWaves"],
        "processes": ["Client-Win64-Shipping.exe"],
    },
    "三角洲行动 (Delta Force)": {
        "platform": ["Other"],
        "paths": ["%LOCALAPPDATA%/DeltaForce", "%USERPROFILE%/AppData/Local/DeltaForce"],
        "processes": ["DeltaForceClient-Win64-Shipping.exe"],
    },
    "永劫无间 (Naraka Bladepoint)": {
        "platform": ["Steam", "Other"],
        "paths": ["%LOCALAPPDATA%/NarakaBladepoint/Saved/SaveGames", "%USERPROFILE%/AppData/Local/NarakaBladepoint"],
        "processes": ["NarakaBladepoint.exe"],
    },
    "英雄联盟 (League of Legends)": {
        "platform": ["Riot"],
        "paths": ["%USERPROFILE%/Documents/League of Legends", "%DOCUMENTS%/League of Legends"],
        "processes": ["League of Legends.exe"],
    },
    "无畏契约 (Valorant)": {
        "platform": ["Riot"],
        "paths": [],
        "processes": ["VALORANT.exe"],
    },
    "CS2 (Counter-Strike 2)": {
        "platform": ["Steam"],
        "paths": ["%USERPROFILE%/Documents/CS2", "%DOCUMENTS%/CS2"],
        "processes": ["cs2.exe"],
    },
    "帕鲁 (Palworld)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%LOCALAPPDATA%/Pal/Saved/SaveGames", "%USERPROFILE%/AppData/Local/Pal/Saved/SaveGames"],
        "processes": ["Palworld-Win64-Shipping.exe"],
    },
    "森林之子 (Sons of the Forest)": {
        "platform": ["Steam"],
        "paths": ["%LOCALAPPDATA%/SonsOfTheForest/Saves", "%USERPROFILE%/AppData/Local/SonsOfTheForest/Saves"],
        "processes": ["SonsOfTheForest.exe"],
    },
    "英灵神殿 (Valheim)": {
        "platform": ["Steam"],
        "paths": ["%USERPROFILE%/AppData/LocalLow/IronGate/Valheim", "%LOCALAPPDATA%/../LocalLow/IronGate/Valheim"],
        "processes": ["valheim.exe"],
    },
    "战地2042 (Battlefield 2042)": {
        "platform": ["Steam", "EA"],
        "paths": ["%DOCUMENTS%/Battlefield 2042", "%USERPROFILE%/Documents/Battlefield 2042"],
        "processes": ["bf2042.exe"],
    },
    "使命召唤：黑色行动6 (BO6)": {
        "platform": ["Steam", "Battle.net", "Xbox"],
        "paths": ["%LOCALAPPDATA%/Call of Duty", "%USERPROFILE%/AppData/Local/Call of Duty"],
        "processes": ["cod.exe"],
    },
    "辐射76 (Fallout 76)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%DOCUMENTS%/My Games/Fallout 76", "%USERPROFILE%/Documents/My Games/Fallout 76"],
        "processes": ["Fallout76.exe"],
    },
    "戴森球计划 (Dyson Sphere Program)": {
        "platform": ["Steam", "GOG"],
        "paths": ["%APPDATA%/Dyson Sphere Program", "%USERPROFILE%/AppData/Roaming/Dyson Sphere Program"],
        "processes": ["DSPGAME.exe"],
    },
    "缺氧 (Oxygen Not Included)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%DOCUMENTS%/Klei/OxygenNotIncluded", "%USERPROFILE%/Documents/Klei/OxygenNotIncluded"],
        "processes": ["OxygenNotIncluded.exe"],
    },
    "饥荒联机版 (Don't Starve Together)": {
        "platform": ["Steam"],
        "paths": ["%DOCUMENTS%/Klei/DoNotStarveTogether", "%USERPROFILE%/Documents/Klei/DoNotStarveTogether"],
        "processes": ["dontstarve_steam.exe"],
    },
    "森林 (The Forest)": {
        "platform": ["Steam"],
        "paths": ["%USERPROFILE%/AppData/LocalLow/SKS/TheForest", "%LOCALAPPDATA%/../LocalLow/SKS/TheForest"],
        "processes": ["TheForest.exe"],
    },
    "绿色地狱 (Green Hell)": {
        "platform": ["Steam"],
        "paths": ["%LOCALAPPDATA%/GreenHell", "%USERPROFILE%/AppData/Local/GreenHell"],
        "processes": ["GreenHell.exe"],
    },
    "深海迷航 (Subnautica)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%USERPROFILE%/AppData/LocalLow/Unknown Worlds/Subnautica", "%LOCALAPPDATA%/../LocalLow/Unknown Worlds/Subnautica"],
        "processes": ["Subnautica.exe"],
    },
    "星际拓荒 (Outer Wilds)": {
        "platform": ["Steam", "Xbox", "Epic"],
        "paths": ["%APPDATA%/OuterWilds", "%USERPROFILE%/AppData/Roaming/OuterWilds"],
        "processes": ["OuterWilds.exe"],
    },
    "极乐迪斯科 (Disco Elysium)": {
        "platform": ["Steam", "GOG"],
        "paths": ["%USERPROFILE%/AppData/LocalLow/ZAUM/Disco Elysium", "%LOCALAPPDATA%/../LocalLow/ZAUM/Disco Elysium"],
        "processes": ["Disco Elysium.exe"],
    },
    "文明6 (Civilization VI)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%LOCALAPPDATA%/Sid Meier's Civilization VI", "%USERPROFILE%/AppData/Local/Sid Meier's Civilization VI"],
        "processes": ["CivilizationVI.exe"],
    },
    "文明7 (Civilization VII)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%LOCALAPPDATA%/Firaxis Games/Civ7", "%USERPROFILE%/AppData/Local/Firaxis Games/Civ7"],
        "processes": ["CivilizationVII.exe"],
    },
    "城市：天际线 (Cities: Skylines)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%LOCALAPPDATA%/Colossal Order/Cities_Skylines", "%USERPROFILE%/AppData/Local/Colossal Order/Cities_Skylines"],
        "processes": ["Cities.exe"],
    },
    "城市：天际线2 (Cities: Skylines II)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%LOCALAPPDATA%/Colossal Order/Cities Skylines II", "%USERPROFILE%/AppData/Local/Colossal Order/Cities Skylines II"],
        "processes": ["Cities2.exe"],
    },
    "群星 (Stellaris)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%DOCUMENTS%/Paradox Interactive/Stellaris", "%USERPROFILE%/Documents/Paradox Interactive/Stellaris"],
        "processes": ["stellaris.exe"],
    },
    "钢铁雄心4 (Hearts of Iron IV)": {
        "platform": ["Steam"],
        "paths": ["%DOCUMENTS%/Paradox Interactive/Hearts of Iron IV", "%USERPROFILE%/Documents/Paradox Interactive/Hearts of Iron IV"],
        "processes": ["hoi4.exe"],
    },
    "十字军之王3 (Crusader Kings III)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%DOCUMENTS%/Paradox Interactive/Crusader Kings III", "%USERPROFILE%/Documents/Paradox Interactive/Crusader Kings III"],
        "processes": ["ck3.exe"],
    },
    "维多利亚3 (Victoria 3)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%DOCUMENTS%/Paradox Interactive/Victoria 3", "%USERPROFILE%/Documents/Paradox Interactive/Victoria 3"],
        "processes": ["victoria3.exe"],
    },
    "双点医院 (Two Point Hospital)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%USERPROFILE%/AppData/LocalLow/Two Point Studios/Two Point Hospital", "%LOCALAPPDATA%/../LocalLow/Two Point Studios/Two Point Hospital"],
        "processes": ["TwoPointHospital.exe"],
    },
    "双点校园 (Two Point Campus)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%USERPROFILE%/AppData/LocalLow/Two Point Studios/Two Point Campus", "%LOCALAPPDATA%/../LocalLow/Two Point Studios/Two Point Campus"],
        "processes": ["TwoPointCampus.exe"],
    },
    "模拟人生4 (The Sims 4)": {
        "platform": ["Steam", "EA"],
        "paths": ["%DOCUMENTS%/Electronic Arts/The Sims 4", "%USERPROFILE%/Documents/Electronic Arts/The Sims 4"],
        "processes": ["TS4_x64.exe"],
    },
    "波西亚时光 (My Time at Portia)": {
        "platform": ["Steam"],
        "paths": ["%APPDATA%/My Time At Portia", "%USERPROFILE%/AppData/Roaming/My Time At Portia"],
        "processes": ["MyTimeAtPortia.exe"],
    },
    "沙石镇时光 (My Time at Sandrock)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%APPDATA%/My Time At Sandrock", "%USERPROFILE%/AppData/Roaming/My Time At Sandrock"],
        "processes": ["Sandrock.exe"],
    },
    "暖雪 (Warm Snow)": {
        "platform": ["Steam"],
        "paths": ["%LOCALAPPDATA%/WarmSnow", "%USERPROFILE%/AppData/Local/WarmSnow"],
        "processes": ["WarmSnow.exe"],
    },
    "土豆兄弟 (Brotato)": {
        "platform": ["Steam"],
        "paths": ["%APPDATA%/Brotato", "%USERPROFILE%/AppData/Roaming/Brotato"],
        "processes": ["Brotato.exe"],
    },
    "以撒的结合 (The Binding of Isaac)": {
        "platform": ["Steam", "GOG"],
        "paths": ["%DOCUMENTS%/My Games/Binding of Isaac Repentance", "%USERPROFILE%/Documents/My Games/Binding of Isaac Repentance"],
        "processes": ["isaac-ng.exe"],
    },
    "挺进地牢 (Enter the Gungeon)": {
        "platform": ["Steam"],
        "paths": ["%USERPROFILE%/AppData/LocalLow/Dodge Roll/Enter the Gungeon", "%LOCALAPPDATA%/../LocalLow/Dodge Roll/Enter the Gungeon"],
        "processes": ["EnterTheGungeon.exe"],
    },
    "雨中冒险2 (Risk of Rain 2)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%USERPROFILE%/AppData/LocalLow/Hopoo Games/Risk of Rain 2", "%LOCALAPPDATA%/../LocalLow/Hopoo Games/Risk of Rain 2"],
        "processes": ["Risk of Rain 2.exe"],
    },
    "星之海 (Sea of Stars)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%LOCALAPPDATA%/SeaOfStars", "%USERPROFILE%/AppData/Local/SeaOfStars"],
        "processes": ["SeaOfStars.exe"],
    },
    "堕落之主 (Lords of the Fallen)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%LOCALAPPDATA%/LOTF2/Saved/SaveGames", "%USERPROFILE%/AppData/Local/LOTF2"],
        "processes": ["LOTF2.exe"],
    },
    "古墓丽影：暗影 (Shadow of the Tomb Raider)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%DOCUMENTS%/Shadow of the Tomb Raider", "%USERPROFILE%/Documents/Shadow of the Tomb Raider"],
        "processes": ["SOTTR.exe"],
    },
    "古墓丽影：崛起 (Rise of the Tomb Raider)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%DOCUMENTS%/Rise of the Tomb Raider", "%USERPROFILE%/Documents/Rise of the Tomb Raider"],
        "processes": ["ROTTR.exe"],
    },
    "控制 (Control)": {
        "platform": ["Steam", "Epic", "GOG"],
        "paths": ["%LOCALAPPDATA%/Control", "%USERPROFILE%/AppData/Local/Control"],
        "processes": ["Control.exe"],
    },
    "心灵杀手2 (Alan Wake 2)": {
        "platform": ["Epic", "Steam"],
        "paths": ["%LOCALAPPDATA%/Remedy/AlanWake2", "%USERPROFILE%/AppData/Local/Remedy/AlanWake2"],
        "processes": ["AlanWake2.exe"],
    },
    "量子破碎 (Quantum Break)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%USERPROFILE%/AppData/Local/Packages/Microsoft.QuantumBreak_8wekyb3d8bbwe", "%LOCALAPPDATA%/Packages/Microsoft.QuantumBreak_8wekyb3d8bbwe"],
        "processes": ["QuantumBreak.exe"],
    },
    "极限竞速：地平线5 (Forza Horizon 5)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%DOCUMENTS%/Forza Horizon 5", "%USERPROFILE%/Documents/Forza Horizon 5"],
        "processes": ["ForzaHorizon5.exe"],
    },
    "极限竞速：地平线4 (Forza Horizon 4)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%DOCUMENTS%/Forza Horizon 4", "%USERPROFILE%/Documents/Forza Horizon 4"],
        "processes": ["ForzaHorizon4.exe"],
    },
    "微软模拟飞行 (MSFS 2020)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%LOCALAPPDATA%/Packages/Microsoft.FlightSimulator_8wekyb3d8bbwe/LocalState", "%USERPROFILE%/AppData/Local/Packages/Microsoft.FlightSimulator_8wekyb3d8bbwe/LocalState"],
        "processes": ["FlightSimulator.exe"],
    },
    "战争机器5 (Gears 5)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%LOCALAPPDATA%/Gears5", "%USERPROFILE%/AppData/Local/Gears5"],
        "processes": ["Gears5.exe"],
    },
    "光环：士官长合集 (Halo MCC)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%LOCALAPPDATA%/HaloInfinite", "%USERPROFILE%/AppData/Local/HaloInfinite"],
        "processes": ["MCC-Win64-Shipping.exe"],
    },
    "光环：无限 (Halo Infinite)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%DOCUMENTS%/Halo Infinite", "%USERPROFILE%/Documents/Halo Infinite"],
        "processes": ["HaloInfinite.exe"],
    },
    "战争雷霆 (War Thunder)": {
        "platform": ["Steam", "Other"],
        "paths": ["%DOCUMENTS%/WarThunder", "%USERPROFILE%/Documents/WarThunder"],
        "processes": ["aces.exe"],
    },
    "坦克世界 (World of Tanks)": {
        "platform": ["Other"],
        "paths": ["%APPDATA%/wargaming.net/WoT", "%USERPROFILE%/AppData/Roaming/wargaming.net/WoT"],
        "processes": ["WoTLauncher.exe"],
    },
    "战舰世界 (World of Warships)": {
        "platform": ["Other"],
        "paths": ["%APPDATA%/wargaming.net/WorldOfWarships", "%USERPROFILE%/AppData/Roaming/wargaming.net/WorldOfWarships"],
        "processes": ["WorldOfWarships.exe"],
    },
    "原子之心 (Atomic Heart)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%LOCALAPPDATA%/AtomicHeart/Saved/SaveGames", "%USERPROFILE%/AppData/Local/AtomicHeart"],
        "processes": ["AtomicHeart.exe"],
    },
    "黑神话：悟空 (Black Myth: Wukong)": {
        "platform": ["Steam", "Epic", "WeGame"],
        "paths": ["%LOCALAPPDATA%/b1/Saved/SaveGames", "%USERPROFILE%/AppData/Local/b1/Saved/SaveGames"],
        "processes": ["b1-Win64-Shipping.exe"],
    },
    "寂静岭2重制版 (Silent Hill 2)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%LOCALAPPDATA%/SilentHill2/Saved/SaveGames", "%USERPROFILE%/AppData/Local/SilentHill2"],
        "processes": ["SH2-Win64-Shipping.exe"],
    },
    "生化危机2重制版 (RE2 Remake)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%LOCALAPPDATA%/RE2", "%USERPROFILE%/AppData/Local/RE2"],
        "processes": ["re2.exe"],
    },
    "生化危机3重制版 (RE3 Remake)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%LOCALAPPDATA%/RE3", "%USERPROFILE%/AppData/Local/RE3"],
        "processes": ["re3.exe"],
    },
    "生化危机7 (RE7)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%LOCALAPPDATA%/RE7", "%USERPROFILE%/AppData/Local/RE7"],
        "processes": ["re7.exe"],
    },
    "木卫四协议 (The Callisto Protocol)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%USERPROFILE%/Saved Games/CallistoProtocol", "%SAVED_GAMES%/CallistoProtocol"],
        "processes": ["CallistoProtocol-Win64-Shipping.exe"],
    },
    "死亡空间重制版 (Dead Space)": {
        "platform": ["Steam", "Epic", "Xbox"],
        "paths": ["%DOCUMENTS%/Dead Space", "%USERPROFILE%/Documents/Dead Space"],
        "processes": ["Dead Space.exe"],
    },
    "潜水员戴夫 (Dave the Diver)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%LOCALAPPDATA%/DAVE THE DIVER", "%USERPROFILE%/AppData/Local/DAVE THE DIVER"],
        "processes": ["DaveTheDiver.exe"],
    },
    "咩咩启示录 (Cult of the Lamb)": {
        "platform": ["Steam", "GOG"],
        "paths": ["%USERPROFILE%/AppData/LocalLow/Massive Monster/Cult Of The Lamb", "%LOCALAPPDATA%/../LocalLow/Massive Monster/Cult Of The Lamb"],
        "processes": ["CultOfTheLamb.exe"],
    },
    "邪恶冥刻 (Inscryption)": {
        "platform": ["Steam", "GOG"],
        "paths": ["%LOCALAPPDATA%/Inscryption", "%USERPROFILE%/AppData/Local/Inscryption"],
        "processes": ["Inscryption.exe"],
    },
    "孤岛惊魂6 (Far Cry 6)": {
        "platform": ["Steam", "Epic", "Ubisoft"],
        "paths": ["%DOCUMENTS%/My Games/Far Cry 6", "%USERPROFILE%/Documents/My Games/Far Cry 6"],
        "processes": ["FarCry6.exe"],
    },
    "刺客信条：影 (Assassin's Creed Shadows)": {
        "platform": ["Steam", "Ubisoft"],
        "paths": ["%DOCUMENTS%/My Games/Assassin's Creed Shadows", "%USERPROFILE%/Documents/My Games/Assassin's Creed Shadows"],
        "processes": ["Assassin's Creed Shadows.exe"],
    },
    "刺客信条：英灵殿 (AC Valhalla)": {
        "platform": ["Steam", "Epic", "Ubisoft"],
        "paths": ["%DOCUMENTS%/My Games/Assassin's Creed Valhalla", "%USERPROFILE%/Documents/My Games/Assassin's Creed Valhalla"],
        "processes": ["ACValhalla.exe"],
    },
    "刺客信条：奥德赛 (AC Odyssey)": {
        "platform": ["Steam", "Epic", "Ubisoft"],
        "paths": ["%DOCUMENTS%/My Games/Assassin's Creed Odyssey", "%USERPROFILE%/Documents/My Games/Assassin's Creed Odyssey"],
        "processes": ["ACOdyssey.exe"],
    },
    "看门狗：军团 (Watch Dogs Legion)": {
        "platform": ["Steam", "Epic", "Ubisoft"],
        "paths": ["%DOCUMENTS%/My Games/Watch Dogs Legion", "%USERPROFILE%/Documents/My Games/Watch Dogs Legion"],
        "processes": ["WatchDogsLegion.exe"],
    },
    "幽灵行动：断点 (Ghost Recon Breakpoint)": {
        "platform": ["Steam", "Epic", "Ubisoft"],
        "paths": ["%DOCUMENTS%/My Games/Ghost Recon Breakpoint", "%USERPROFILE%/Documents/My Games/Ghost Recon Breakpoint"],
        "processes": ["GRB.exe"],
    },
    "全境封锁2 (The Division 2)": {
        "platform": ["Epic", "Ubisoft"],
        "paths": ["%DOCUMENTS%/My Games/The Division 2", "%USERPROFILE%/Documents/My Games/The Division 2"],
        "processes": ["TheDivision2.exe"],
    },
    "彩虹六号：围攻 (Rainbow Six Siege)": {
        "platform": ["Steam", "Epic", "Ubisoft"],
        "paths": ["%DOCUMENTS%/My Games/Rainbow Six - Siege", "%USERPROFILE%/Documents/My Games/Rainbow Six - Siege"],
        "processes": ["RainbowSix.exe"],
    },
    "猎杀对决 (Hunt: Showdown)": {
        "platform": ["Steam"],
        "paths": ["%USERPROFILE%/AppData/LocalLow/Crytek/Hunt Showdown", "%LOCALAPPDATA%/../LocalLow/Crytek/Hunt Showdown"],
        "processes": ["HuntGame.exe"],
    },
    "铁拳8 (Tekken 8)": {
        "platform": ["Steam", "Xbox"],
        "paths": ["%LOCALAPPDATA%/TEKKEN 8/Saved/SaveGames", "%USERPROFILE%/AppData/Local/TEKKEN 8"],
        "processes": ["TEKKEN 8.exe"],
    },
    "街头霸王6 (Street Fighter 6)": {
        "platform": ["Steam"],
        "paths": ["%APPDATA%/StreetFighter6", "%USERPROFILE%/AppData/Roaming/StreetFighter6"],
        "processes": ["StreetFighter6.exe"],
    },
    "拳皇15 (KOF XV)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%LOCALAPPDATA%/KOFXV/Saved/SaveGames", "%USERPROFILE%/AppData/Local/KOFXV"],
        "processes": ["KOFXV.exe"],
    },
    "王国之心3 (Kingdom Hearts III)": {
        "platform": ["Steam", "Epic"],
        "paths": ["%DOCUMENTS%/KINGDOM HEARTS III", "%USERPROFILE%/Documents/KINGDOM HEARTS III"],
        "processes": ["KINGDOM HEARTS III.exe"],
    },
}


def get_rules() -> dict:
    """返回内置规则（过滤掉 None 占位）。"""
    return {k: v for k, v in GAME_RULES.items() if v}


# ============ Steam AppID 映射（用于在线匹配 Steam 游戏图标） ============
# 游戏名（与 GAME_RULES 键一致） -> Steam AppID
# 仅列出可确定的 AppID；未收录的游戏前端会回退到默认图标。
# 图标 URL: https://cdn.akamai.steamstatic.com/steam/apps/<appid>/header.jpg
STEAM_APPIDS = {
    "艾尔登法环 (Elden Ring)": 1245620,
    "博德之门3 (Baldur's Gate 3)": 1086940,
    "终焉之莉莉 (Ender Lilies)": 1121530,
    "无人深空 (No Man's Sky)": 275850,
    "奥日与黑暗森林 (Ori and the Blind Forest)": 261550,
    "巫师3 (The Witcher 3)": 292030,
    "赛博朋克2077 (Cyberpunk 2077)": 1091500,
    "哈迪斯2 (Hades II)": 1145350,
    "天国拯救2 (Kingdom Come: Deliverance II)": 1771300,
    "神之天平 (ASTLIBRA)": 1716740,
    "战锤40K：暗潮 (Darktide)": 1361210,
    "战锤：末世鼠疫2 (Vermintide 2)": 552500,
    "八方旅人2 (Octopath Traveler II)": 1971650,
    "勇者斗恶龙11S": 742120,
    "最终幻想7 重制版 (FF7 Remake)": 1462040,
    "最终幻想14 (FF14)": 39210,
    "尼尔：机械纪元 (Nier Automata)": 524220,
    "生化危机4重制版 (RE4 Remake)": 2050650,
    "生化危机8 (Resident Evil Village)": 1196590,
    "怪物猎人：世界 (MH World)": 582010,
    "怪物猎人：崛起 (MH Rise)": 1446780,
    "黑暗之魂3 (Dark Souls III)": 374320,
    "只狼 (Sekiro)": 814380,
    "对马岛之魂 (Ghost of Tsushima)": 2215430,
    "战神 (God of War)": 1593500,
    "战神：诸神黄昏 (God of War Ragnarok)": 2322010,
    "地平线：零之曙光 (Horizon Zero Dawn)": 1151640,
    "地平线：西之绝境 (Horizon Forbidden West)": 2420110,
    "漫威蜘蛛侠 (Marvel's Spider-Man)": 1817070,
    "荒野大镖客2 (Red Dead Redemption 2)": 1174180,
    "GTA5 (Grand Theft Auto V)": 271590,
    "泰坦陨落2 (Titanfall 2)": 1237970,
    "Apex英雄 (Apex Legends)": 1172470,
    "双人成行 (It Takes Two)": 1426210,
    "逃出生天 (A Way Out)": 1222700,
    "星空 (Starfield)": 1716740,
    "上古卷轴5 (Skyrim SE)": 489830,
    "辐射4 (Fallout 4)": 377160,
    "消逝的光芒2 (Dying Light 2)": 534380,
    "消逝的光芒 (Dying Light)": 239140,
    "霍格沃茨之遗 (Hogwarts Legacy)": 990080,
    "星露谷物语 (Stardew Valley)": 413150,
    "泰拉瑞亚 (Terraria)": 105600,
    "空洞骑士 (Hollow Knight)": 367520,
    "蔚蓝 (Celeste)": 504230,
    "死亡细胞 (Dead Cells)": 588650,
    "哈迪斯 (Hades)": 1145360,
    "吸血鬼幸存者 (Vampire Survivors)": 1794680,
    "杀戮尖塔 (Slay the Spire)": 646570,
    "遗迹2 (Remnant II)": 1282100,
    "仁王2 (Nioh 2)": 1325200,
    "卧龙：苍天陨落 (Wo Long)": 1448440,
    "匹诺曹的谎言 (Lies of P)": 1627720,
    "暗黑破坏神4 (Diablo IV)": 2344520,
    "暗黑破坏神2重制版 (D2R)": 1394580,
    "永劫无间 (Naraka Bladepoint)": 1203220,
    "CS2 (Counter-Strike 2)": 730,
    "帕鲁 (Palworld)": 1623730,
    "森林之子 (Sons of the Forest)": 1326470,
    "英灵神殿 (Valheim)": 892970,
    "战地2042 (Battlefield 2042)": 1517290,
    "辐射76 (Fallout 76)": 1151340,
    "戴森球计划 (Dyson Sphere Program)": 1366540,
    "缺氧 (Oxygen Not Included)": 457140,
    "饥荒联机版 (Don't Starve Together)": 322330,
    "森林 (The Forest)": 242760,
    "绿色地狱 (Green Hell)": 815370,
    "深海迷航 (Subnautica)": 264710,
    "星际拓荒 (Outer Wilds)": 753880,
    "极乐迪斯科 (Disco Elysium)": 632470,
    "文明6 (Civilization VI)": 289070,
    "文明7 (Civilization VII)": 1295660,
    "城市：天际线 (Cities: Skylines)": 255710,
    "城市：天际线2 (Cities: Skylines II)": 949230,
    "群星 (Stellaris)": 281990,
    "钢铁雄心4 (Hearts of Iron IV)": 394360,
    "十字军之王3 (Crusader Kings III)": 1158310,
    "维多利亚3 (Victoria 3)": 529340,
    "双点医院 (Two Point Hospital)": 535930,
    "双点校园 (Two Point Campus)": 1642380,
    "模拟人生4 (The Sims 4)": 1222670,
    "波西亚时光 (My Time at Portia)": 666140,
    "沙石镇时光 (My Time at Sandrock)": 1401590,
    "暖雪 (Warm Snow)": 1296830,
    "土豆兄弟 (Brotato)": 1942280,
    "以撒的结合 (The Binding of Isaac)": 250900,
    "挺进地牢 (Enter the Gungeon)": 311690,
    "雨中冒险2 (Risk of Rain 2)": 632360,
    "星之海 (Sea of Stars)": 1244090,
    "堕落之主 (Lords of the Fallen)": 1501750,
    "古墓丽影：暗影 (Shadow of the Tomb Raider)": 750920,
    "古墓丽影：崛起 (Rise of the Tomb Raider)": 391220,
    "控制 (Control)": 870780,
    "心灵杀手2 (Alan Wake 2)": 1439510,
    "量子破碎 (Quantum Break)": 474960,
    "极限竞速：地平线5 (Forza Horizon 5)": 1551360,
    "极限竞速：地平线4 (Forza Horizon 4)": 1293830,
    "微软模拟飞行 (MSFS 2020)": 1250410,
    "战争机器5 (Gears 5)": 1097840,
    "光环：士官长合集 (Halo MCC)": 976730,
    "光环：无限 (Halo Infinite)": 1240440,
    "战争雷霆 (War Thunder)": 236390,
    "原子之心 (Atomic Heart)": 668580,
    "黑神话：悟空 (Black Myth: Wukong)": 2358720,
    "寂静岭2重制版 (Silent Hill 2)": 2124490,
    "生化危机2重制版 (RE2 Remake)": 883710,
    "生化危机3重制版 (RE3 Remake)": 952060,
    "生化危机7 (RE7)": 418370,
    "木卫四协议 (The Callisto Protocol)": 1542140,
    "死亡空间重制版 (Dead Space)": 1693980,
    "潜水员戴夫 (Dave the Diver)": 1868140,
    "咩咩启示录 (Cult of the Lamb)": 1313140,
    "邪恶冥刻 (Inscryption)": 1092790,
    "孤岛惊魂6 (Far Cry 6)": 2369390,
    "刺客信条：影 (Assassin's Creed Shadows)": 2679850,
    "刺客信条：英灵殿 (AC Valhalla)": 2208920,
    "刺客信条：奥德赛 (AC Odyssey)": 812140,
    "彩虹六号：围攻 (Rainbow Six Siege)": 359550,
    "猎杀对决 (Hunt: Showdown)": 594650,
    "铁拳8 (Tekken 8)": 1778820,
    "街头霸王6 (Street Fighter 6)": 1364780,
    "拳皇15 (KOF XV)": 1498570,
    "王国之心3 (Kingdom Hearts III)": 2552430,
}


def get_steam_appid(game_name: str):
    """按游戏名查 Steam AppID（找不到返回 None）。"""
    return STEAM_APPIDS.get(game_name)
