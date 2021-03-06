#!/usr/bin/env python3

import json
import sys


def resolve_path(map_path, image_path):
    map_path_parts = map_path.split("/")[:-1]
    image_path_parts = image_path.split("/")
    final_path = map_path_parts
    for image_path_part in image_path_parts:
        if image_path_part == "..":
            del final_path[-1]
        else:
            final_path.append(image_path_part)
    return "/".join(final_path)

def insert_floor_layer():
    global merged_map
    floor_layer = {}
    floor_layer["draworder"] = "topdown"
    floor_layer["id"] = 4
    floor_layer["name"] = "floorLayer"
    floor_layer["objects"] = []
    floor_layer["opacity"] = 1
    floor_layer["type"] = "objectgroup"
    floor_layer["visible"] = True
    floor_layer["x"] = 0
    floor_layer["y"] = 0
    merged_map["layers"].append(floor_layer)

def insert_background_layer():
    global merged_map
    background_layer = {}
    background_layer["height"] = merged_map["height"]
    background_layer["id"] = merged_map["nextlayerid"]
    merged_map["nextlayerid"] += 1
    background_layer["name"] = "global background"
    background_layer["opacity"] = 1
    background_layer["type"] = "tilelayer"
    background_layer["visible"] = True
    background_layer["width"] = merged_map["width"]
    background_layer["x"] = 0
    background_layer["y"] = 0

    infill = get_tile_gid("src/tiles/floor_gaffa.png", 1)
    border = get_tile_gid("src/tiles/floor_gaffa.png", 2)

    background_layer["data"] = [infill] * merged_map["height"] * merged_map["width"]

    for x in range(1, merged_map["width"]-1):
        y = 0
        background_layer["data"][y * merged_map["width"] + x] = border

    for x in range(1, merged_map["width"]-1):
        y = merged_map["height"]-1
        background_layer["data"][y * merged_map["width"] + x] = border | 0x40000000

    for y in range(1, merged_map["height"]-1):
        x = 0
        background_layer["data"][y * merged_map["width"] + x] = border | 0x20000000

    for y in range(1, merged_map["height"]-1):
        x = merged_map["width"]-1
        background_layer["data"][y * merged_map["width"] + x] = border | 0xA0000000

    x = 0
    y = 0
    background_layer["data"][y * merged_map["width"] + x] = infill | 0x20000000

    x = merged_map["width"]-1
    y = 0
    background_layer["data"][y * merged_map["width"] + x] = infill

    x = 0
    y = merged_map["height"]-1
    background_layer["data"][y * merged_map["width"] + x] = infill | 0xa0000000

    x = merged_map["width"]-1
    y = merged_map["height"]-1
    background_layer["data"][y * merged_map["width"] + x] = infill | 0x40000000

    merged_map["layers"].insert(0, background_layer)

def get_layer_index(previous_layer_name):
    global merged_map
    if previous_layer_name is None:
        return 0
    for i in range(len(merged_map["layers"])):
        if merged_map["layers"][i]["name"] == previous_layer_name:
            return i + 1

def merge_tilesets(tilesets, map_path):
    tileset_map = {}
    global merged_map, merged_map_next_tileset_gid
    for tileset in tilesets:
        if "image" in tileset:
            tileset["image"] = resolve_path(map_path, tileset["image"])
        else:
            print("tileset in", map_path, "not embedded")
            sys.exit(1)
        found = False
        merged_tileset_start = -1
        for merged_tileset in merged_map["tilesets"]:
            if tileset["image"] == merged_tileset["image"]:
                found = True
                merged_tileset_start = merged_tileset["firstgid"]
                break
        if found:
            for i in range(tileset["tilecount"]):
                tileset_map[tileset["firstgid"] + i] = merged_tileset_start + i
        else:
            for i in range(tileset["tilecount"]):
                tileset_map[tileset["firstgid"] + i] = merged_map_next_tileset_gid + i
            tileset["firstgid"] = merged_map_next_tileset_gid
            merged_map_next_tileset_gid += tileset["tilecount"]
            merged_map["tilesets"].append(tileset)
    return tileset_map

def get_tile_gid(tileset_path, tileset_id):
    global merged_map
    for tileset in merged_map["tilesets"]:
        if tileset["image"] == tileset_path:
            return tileset["firstgid"] + tileset_id
    return -1

def get_tile_properties(tileset_path, tileset_id):
    global merged_map
    for tileset in merged_map["tilesets"]:
        if tileset["image"] == tileset_path:
            if not "tiles" in tileset:
                break
            for tile in tileset["tiles"]:
                if tile["id"] == tileset_id:
                    if "properties" in tile:
                        return tile["properties"]
            break
    return []

def apply_tileset_map(tileset_map, value):
    mask = 0xE0000000
    result = value
    try:
        result = tileset_map[value & ~ mask]
    except KeyError:
        return result
    result = result ^ (value & mask)
    return result

def merge_tilelayer(layer, m, tileset_map, previous_layer_name):
    global merged_map, min_x, min_y
    found = False
    for merged_layer in merged_map["layers"]:
        if merged_layer["name"] == layer["name"]:
            found = True
            for x in range(m["width"]):
                merged_x = m["offset_x"] - min_x + x
                for y in range(m["height"]):
                    merged_y = m["offset_y"] - min_y + y
                    merged_pos = merged_y * merged_layer["width"] + merged_x
                    layer_pos = y * layer["width"] + x
                    merged_layer["data"][merged_pos] = apply_tileset_map(tileset_map, layer["data"][layer_pos])
            break
    if not found:
        new_layer = {}
        new_layer["data"] = [0] * merged_map["height"] * merged_map["width"]
        new_layer["height"] = merged_map["height"]
        new_layer["id"] = merged_map["nextlayerid"]
        merged_map["nextlayerid"] += 1
        new_layer["name"] = layer["name"]
        new_layer["opacity"] = layer["opacity"]
        if "properties" in layer:
            new_layer["properties"] = layer["properties"]
            for property in new_layer["properties"]:
                if property["name"] == "playAudio":
                    if property["value"].startswith("http:"):
                        continue
                    if property["value"].startswith("https:"):
                        continue
                    if property["value"].startswith("stream:"):
                        continue
                    property["value"] = resolve_path(m["path"], property["value"])
        new_layer["startx"] = 0
        new_layer["starty"] = 0
        new_layer["type"] = "tilelayer"
        new_layer["visible"] = layer["visible"]
        new_layer["width"] = merged_map["width"]
        new_layer["x"] = 0
        new_layer["y"] = 0
        for x in range(m["width"]):
            merged_x = m["offset_x"] - min_x + x
            for y in range(m["height"]):
                merged_y = m["offset_y"] - min_y + y
                merged_pos = merged_y * new_layer["width"] + merged_x
                layer_pos = y * layer["width"] + x
                new_layer["data"][merged_pos] = apply_tileset_map(tileset_map, layer["data"][layer_pos])
        merged_map["layers"].insert(
                get_layer_index(previous_layer_name),
                new_layer
                )


merged_map = {}
merged_map["compressionlevel"] = -1
merged_map["infinite"] = False
merged_map["layers"] = []
merged_map["nextlayerid"] = 1
merged_map["nextobjectid"] = 1
merged_map["orientation"] = "orthogonal"
merged_map["renderorder"] = "right-down"
merged_map["tileheight"] = 32
merged_map["tilesets"] = []
merged_map["tilewidth"] = 32
merged_map["type"] = "map"
merged_map["version"] = 1.4
merged_map_next_tileset_gid = 1

min_x = 0
max_x = 0
min_y = 0
max_y = 0

map_parts = []

merge_config = json.load(open("merge_config.json", "r"))

merge_tilesets(merge_config["tilesets"], "")

for m in merge_config["maps"]:
    map_data = json.load(open(m["path"], "r"))
    if map_data["infinite"]:
        print("skipping map", m["path"], "(can't handle infinite maps)")
        continue
    if map_data["compressionlevel"] != -1:
        print("skipping map", m["path"], "(can't handle compression at the moment)")
        continue
    map_data["path"] = m["path"]
    map_data["offset_x"] = m["x"] + merge_config["border_size"]
    map_data["offset_y"] = m["y"] + merge_config["border_size"]
    map_parts.append(map_data)
    if m["x"] < min_x:
        min_x = m["x"]
    if m["y"] < min_y:
        min_y = m["y"]
    if m["x"] + map_data["width"] > max_x:
        max_x = m["x"] + map_data["width"]
    if m["y"] + map_data["height"] > max_y:
        max_y = m["y"] + map_data["height"]

print("min_x:", min_x, "max_x:", max_x)
print("min_y:", min_y, "max_y:", max_y)
merged_map["width"] = max_x - min_x + 2 * merge_config["border_size"]
merged_map["height"] = max_y - min_y + 2 * merge_config["border_size"]
print("map size: ", merged_map["width"], "x", merged_map["height"])

first_map = True

insert_floor_layer()

for m in map_parts:
    tileset_map = merge_tilesets(m["tilesets"], m["path"])
    previous_layer_name = None

    # merge layers
    for layer in m["layers"]:
        if "compression" in layer and layer["compression"] != "":
            print("skipping layer", layer["name"], "because it is compressed")
            continue
        if layer["type"] == "tilelayer":
            if layer["name"] == "start" and not first_map:
                continue
            merge_tilelayer(layer, m, tileset_map, previous_layer_name)
            previous_layer_name = layer["name"]
        elif layer["type"] == "objectgroup" and layer["name"] == "floorLayer":
            previous_layer_name = layer["name"]
            continue
        else:
            print("skipping layer", layer["name"], "(can't handle", layer["type"], "yet)")
            continue
    first_map = False

# apply hidden tiles
empty_tile_gid = get_tile_gid("src/tiles/empty.png", 0)
empty_collides_tile_gid = get_tile_gid("src/tiles/empty.png", 1)
tileset_map = {}
for tileset in merge_config["hidden_tiles"]:
    path = tileset["tileset"]
    ids = tileset["ids"]
    for i in ids:
        properties = get_tile_properties(path, i)
        collides = False
        for p in properties:
            if p["name"] == "collides":
                if p["value"]:
                    collides = True
        tileset_map[get_tile_gid(path, i)] = empty_collides_tile_gid if collides else empty_tile_gid

for layer in merged_map["layers"]:
    if not layer["type"] == "tilelayer":
        continue
    for i in range(len(layer["data"])):
        layer["data"][i] = apply_tileset_map(tileset_map, layer["data"][i])

insert_background_layer()
json.dump(merged_map, open("main.json", "w"))
