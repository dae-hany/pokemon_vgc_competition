shader_type spatial;
render_mode unshaded, cull_disabled;

uniform sampler2D albedo_texture : source_color, filter_nearest;
uniform float grayscale : hint_range(0.0, 1.0) = 0.0;

void fragment() {
    vec4 tex_color = texture(albedo_texture, UV);
    float gray = dot(tex_color.rgb, vec3(0.299, 0.587, 0.114));
    vec3 final_color = mix(tex_color.rgb, vec3(gray), grayscale);

    ALBEDO = final_color;
    ALPHA = tex_color.a;
}
