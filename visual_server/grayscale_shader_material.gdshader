shader_type spatial;

uniform sampler2D albedo_texture : source_color;
uniform float grayscale : hint_range(0.0, 1.0) = 0.0;

void fragment() {
    ivec2 tex_size = textureSize(albedo_texture, 0);
    vec2 tex_size_f = vec2(tex_size);
    vec2 pixel_uv = (floor(UV * tex_size_f) + 0.5) / tex_size_f;
    vec4 tex_color = texture(albedo_texture, pixel_uv);
    float gray = dot(tex_color.rgb, vec3(0.299, 0.587, 0.114));
    vec3 final_color = mix(tex_color.rgb, vec3(gray), grayscale);
    ALBEDO = final_color;
    ALPHA = tex_color.a;
}