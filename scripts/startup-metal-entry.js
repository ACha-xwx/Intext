// Build-only entry. Runtime uses the local IIFE bundle and never contacts npm/CDNs.
import {ShaderMount,liquidMetalFragmentShader} from "@paper-design/shaders";

window.intextLiquidMetal={
  mount(element,speed=0.6){
    return new ShaderMount(element,liquidMetalFragmentShader,{
      u_repetition:4,u_softness:0.5,u_shiftRed:0.3,u_shiftBlue:0.3,
      u_distortion:0,u_contour:0,u_angle:45,u_scale:8,u_shape:1,
      u_offsetX:0.1,u_offsetY:-0.1,u_originX:0.5,u_originY:0.5,
      u_fit:1,u_imageAspectRatio:1,u_isImage:false,
      u_colorBack:[0,0,0,0],u_colorTint:[0,0,0,0]
    },undefined,speed);
  }
};
