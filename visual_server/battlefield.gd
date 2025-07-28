extends Node3D

@export var left_sprites: Array[Node3D] = []
@export var right_sprites: Array[Node3D] = []

@onready var network_server: NetworkServer = get_node("NetworkServer")
@onready var fade_screen: FadeScreen = get_node("FadeScreen")

var _is_animating = false

func set_type(sprite: Node3D, type: int, index: int = 0):
	sprite.get_child(0).texture = load("res://sprites/pkm/" + Global.TYPE_TO_STRINGS[type][index])

func attack(sprite: Node3D, duration: float = 0.25):
	Global.text_box.show_message("Perform attack!")
	await Global.text_box.text_finished
	var tween = create_tween()
	tween.tween_property(sprite.get_child(0), "rotation_degrees:z", 45, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tween.tween_property(sprite.get_child(0), "rotation_degrees:z", 0, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT).set_delay(duration)
	await tween.finished

func switch(sprite_a: Node3D, sprite_b: Node3D, duration: float = 1.5):
	Global.text_box.show_message("Switch!")
	await Global.text_box.text_finished
	var pos_a = sprite_a.global_position
	var pos_b = sprite_b.global_position
	var tween = create_tween()
	tween.tween_property(sprite_a, "global_position", pos_b, duration)
	tween.parallel().tween_property(sprite_b, "global_position", pos_a, duration)
	await tween.finished

func damage(sprite: Node3D, offset := 0.05, duration := 0.05, shakes := 6):
	var tween = create_tween()
	var original_pos = sprite.get_child(0).position  # local position
	for i in range(shakes):
		var dir = -1 if i % 2 == 0 else 1
		var target_pos = original_pos + Vector3(offset * dir, 0, 0)
		tween.tween_property(sprite.get_child(0), "position", target_pos, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	# Return to original position smoothly
	tween.tween_property(sprite.get_child(0), "position", original_pos, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tween.finished
	Global.text_box.show_message("Took damage!")
	await Global.text_box.text_finished

func faint(sprite: Node3D, duration: float = 0.5):
	Global.text_box.show_message("Fainted!")
	await Global.text_box.text_finished
	var tween = create_tween()
	tween.tween_property(sprite.get_child(0), "rotation_degrees:z", 90, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tween.tween_interval(0.1)
	await tween.finished

func _process(delta: float) -> void:
	if network_server and not _is_animating and network_server.has_message():
		var msg = network_server.get_next_message()
		_animate_event(msg)

# This needs to be async
func _animate_event(msg: Dictionary):
	_is_animating = true
	match msg.get("event", ""):
		"Battle":
			await _handle_battle(msg)
		"Turn":
			await _handle_turn(msg)
		"Attack":
			await _handle_attack(msg)
		"Damage":
			await _handle_damage(msg)
		"Switch":
			await _handle_switch(msg)
		"Faint":
			await _handle_faint(msg)
		"End":
			await _handle_end(msg)
		_:
			print("Unknown event:", msg)
	_is_animating = false

func _handle_battle(msg: Dictionary):
	if not fade_screen.is_faded_out():
		Global.text_box.text = ""
		await fade_screen.fade_out_in()
	for side in msg["teams"].size():
		var team = msg["teams"][side]
		var sprites = left_sprites if side == 0 else right_sprites
		for i in team["active"].size():
			set_type(sprites[i], int(team["active"][i]["type"]))
			sprites[i].get_child(0).rotation_degrees.z = 0
			sprites[i].get_child(1).health_bar.value = 100.
		for i in team["reserve"].size():
			set_type(sprites[i+2], int(team["reserve"][i]["type"]))
			sprites[i+2].get_child(0).rotation_degrees.z = 0
			sprites[i+2].get_child(1).health_bar.value = 100.
	await fade_screen.fade_out_in()

func _handle_turn(msg: Dictionary):
	var number = int(msg["number"])
	Global.text_box.show_message("Start turn {num}.".format({"num": number}))
	await Global.text_box.text_finished

func _handle_attack(msg: Dictionary):
	var side = int(msg["side"])
	var attacker = int(msg["attacker"])
	var sprites = left_sprites if side == 0 else right_sprites
	await attack(sprites[attacker], 0.1)

func _handle_damage(msg: Dictionary):
	var side = int(msg["side"])
	var defender = int(msg["defender"])
	var hp_rate = msg["hp_rate"]
	var sprites = left_sprites if side == 0 else right_sprites
	await damage(sprites[defender])
	await sprites[defender].get_child(1).set_health(hp_rate * 100)

func _handle_switch(msg: Dictionary):
	var side = int(msg["side"])
	var switch_in = int(msg["switch_in"])
	var switch_out = int(msg["switch_out"]) + 2
	var sprites = left_sprites if side == 0 else right_sprites
	await switch(sprites[switch_out], sprites[switch_in], 0.5)
	var temp = sprites[switch_out]
	sprites[switch_out] = sprites[switch_in]
	sprites[switch_in] = temp

func _handle_faint(msg: Dictionary):
	var side = int(msg["side"])
	var pos = int(msg["pos"])
	var sprites = left_sprites if side == 0 else right_sprites
	await faint(sprites[pos], 0.2)

func _handle_end(msg: Dictionary):
	var side = int(msg["side"])
	Global.text_box.show_message("Battle ended. Player {side} won!".format({"side": side}))
	await Global.text_box.text_finished
	await get_tree().create_timer(3.0).timeout
