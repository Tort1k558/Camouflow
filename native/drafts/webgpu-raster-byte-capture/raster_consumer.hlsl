Texture2D<float4> Source : register(t0);
RWByteAddressBuffer RasterOutput : register(u1);
cbuffer Parameters : register(b0) { uint4 UnusedKey0; uint4 UnusedKey1; uint Width; uint3 Unused; uint4 MoreUnused; };
float4 vertex_main(uint vertex : SV_VertexID) : SV_Position {
    return float4(vertex == 2 ? 3.0 : -1.0, vertex == 1 ? 3.0 : -1.0, 0.0, 1.0);
}
float4 pixel_main(float4 position : SV_Position) : SV_Target {
    const uint2 pixel_position=uint2(position.xy);
    const float4 value=Source.Load(int3(pixel_position,0));
    const uint4 rgba=(uint4)round(saturate(value)*255.0);
    RasterOutput.Store((pixel_position.y*Width+pixel_position.x)*4,rgba.r|(rgba.g<<8)|(rgba.b<<16)|(rgba.a<<24));
    return value;
}
