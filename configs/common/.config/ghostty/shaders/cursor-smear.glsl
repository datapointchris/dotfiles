// Ghostty passes colour uniforms as sRGB component values while the render
// pipeline blends in linear space, so an unconverted cursor colour reads far
// too bright.
vec3 srgbToLinear(vec3 c) {
    return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
}

const float DURATION = 0.12;
const float MIN_TRAVEL_ROWS = 1.2;
const float MAX_REACH_CELLS = 10.0;
const float OPACITY = 0.45;
const float TAIL_OPACITY = 0.12;
const float EDGE_SOFTNESS = 1.5;

// Quadratic rather than cubic: a cubic collapse is front-loaded enough that the
// trail is mostly gone a third of the way in, whatever DURATION says.
float easeOutQuad(float x) {
    return 1.0 - (1.0 - x) * (1.0 - x);
}

// https://iquilezles.org/articles/distfunctions2d/
float sdOrientedBox(vec2 p, vec2 a, vec2 b, float thickness) {
    float len = length(b - a);
    vec2 dir = (b - a) / len;
    vec2 q = p - (a + b) * 0.5;
    q = mat2(dir.x, -dir.y, dir.y, dir.x) * q;
    q = abs(q) - vec2(len, thickness) * 0.5;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0);
}

float sdBox(vec2 p, vec2 center, vec2 halfSize) {
    vec2 d = abs(p - center) - halfSize;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    fragColor = texture(iChannel0, fragCoord / iResolution.xy);

    // Unfocused surfaces render only on sporadic events, so iTimeDelta jumps and
    // the smear would appear frozen at whatever progress it stalled at.
    if (iFocus < 1) return;

    float progress = clamp((iTime - iTimeCursorChange) / DURATION, 0.0, 1.0);
    if (progress >= 1.0) return;

    // .xy is the cursor's -X/+Y corner, in the same frame as fragCoord.
    vec2 size = iCurrentCursor.zw;
    vec2 head = iCurrentCursor.xy + vec2(size.x, -size.y) * 0.5;
    vec2 tail = iPreviousCursor.xy + vec2(iPreviousCursor.z, -iPreviousCursor.w) * 0.5;

    vec2 travel = head - tail;
    float dist = length(travel);

    // A move that changes row lands on whatever column the new line's length
    // allows, so its horizontal component is chosen by the text rather than by
    // the motion. Measuring against the vertical component alone is what keeps
    // j and k quiet in a diff, where neighbouring lines differ by tens of cells
    // and the clamp drags the cursor that far sideways on every keypress. Only
    // the threshold ignores it; the smear is still drawn along the real travel.
    float motion = abs(travel.y) > size.y * 0.5 ? abs(travel.y) : dist;
    // Row height rather than cell width, so stepping down a single line — the
    // most common motion there is — stays below the threshold.
    if (motion < size.y * MIN_TRAVEL_ROWS) return;

    // Clamped so a jump across the screen smears the same distance as a word
    // motion rather than painting a bar the full width of the window.
    vec2 dir = travel / dist;
    float reach = min(dist, size.x * MAX_REACH_CELLS) * (1.0 - easeOutQuad(progress));
    vec2 origin = head - dir * reach;

    // Cross-section of the cursor perpendicular to travel, interpolated for
    // diagonals; the extension makes the smear cover both cursor footprints.
    float thickness = abs(dir.x) * size.y + abs(dir.y) * size.x;
    float extension = 0.5 * (abs(dir.x) * size.x + abs(dir.y) * size.y);

    float smear = sdOrientedBox(fragCoord, origin - dir * extension, head + dir * extension, thickness);
    float alpha = OPACITY * (1.0 - smoothstep(0.0, EDGE_SOFTNESS, smear)) * (1.0 - progress);

    float along = clamp(dot(fragCoord - origin, dir) / max(reach, 1.0), 0.0, 1.0);
    alpha *= mix(TAIL_OPACITY, 1.0, along);

    // Leave the real cursor and its text untouched.
    alpha *= smoothstep(-EDGE_SOFTNESS, 0.0, sdBox(fragCoord, head, size * 0.5));

    fragColor = vec4(mix(fragColor.rgb, srgbToLinear(iCurrentCursorColor.rgb), alpha), fragColor.a);
}
