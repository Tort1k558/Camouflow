Texture2D<float4> Source : register(t0);
float4 vertex_main(uint vertex : SV_VertexID) : SV_Position {
    return float4(vertex == 2 ? 3.0 : -1.0, vertex == 1 ? 3.0 : -1.0, 0.0, 1.0);
}
float4 pixel_main(float4 position : SV_Position) : SV_Target {
    return Source.Load(int3(uint2(position.xy), 0));
}
