import gc
from io import BytesIO
from pathlib import Path
from typing import Optional

import toml
import torch
from diffusers import (
    DDIMScheduler,
    LMSDiscreteScheduler,
    StableDiffusionImg2ImgPipeline,
    StableDiffusionPipeline,
)
from PIL import Image
from torch import autocast

# Load the config file to read in system settings.
base_path = (Path(__file__).parent / "../configs/").resolve()
print(base_path)
app_settings = toml.load(f"{base_path}/settings.toml")


def generate_image_with_prompt(
    input_img_path: Optional[str] = None,
    prompt_txt: str = "Face portrait",
    negative_prompt: str = "",
    n_steps: int = 50,
    guidance_scale: int = 7.5,
    sampler_type: str = "K-LMS",
    output_path: str = None,
):
    # License: https://huggingface.co/spaces/CompVis/stable-diffusion-license
    torch.cuda.empty_cache()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_path = app_settings["PretrainedModels"]["SDVersion"]

    # Default Scheduler K-LMS(Katherine Crowson)
    # TODO Enable ability to switch different Schedulers
    sampler = None
    if sampler_type == "K-LMS":
        sampler = LMSDiscreteScheduler(
            beta_start=0.00085, beta_end=0.012, beta_schedule="scaled_linear"
        )
    elif sampler_type == "DDIM":
        # https://arxiv.org/abs/2010.02502
        sampler = DDIMScheduler(
            beta_start=0.00085,
            beta_end=0.012,
            beta_schedule="scaled_linear",
            clip_sample=False,
            set_alpha_to_one=False,
        )

    if input_img_path:
        pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
            model_path, revision="fp16", torch_dtype=torch.float16
        ).to(device)
        if sampler:
            pipe.scheduler = sampler
        # Open image
        image_input = Image.open(input_img_path).convert("RGB")
        init_image = image_input.resize((512, 512))

        with autocast(device):
            images = pipe(
                prompt=prompt_txt,
                negative_prompt=negative_prompt,
                init_image=init_image,
                strength=0.75,
                guidance_scale=guidance_scale,
                num_inference_steps=n_steps,
            )["sample"]
    else:  # Default prompt
        generator = torch.Generator(device=device).manual_seed(42)
        pipe = StableDiffusionPipeline.from_pretrained(
            model_path, revision="fp16", torch_dtype=torch.float16
        ).to(device)
        if sampler:
            pipe.scheduler = sampler
        with autocast(device):
            # One sample for now.
            # TODO Extend for multiple samples.
            images = pipe(
                prompt=[prompt_txt] * 1,
                negative_prompt=[negative_prompt] * 1,
                num_inference_steps=n_steps,
                guidance_scale=guidance_scale,
                generator=generator,
            ).images

    file_name = output_path + "/result.jpg"
    if output_path:
        images[0].save(file_name)
    # Release resources
    gc.collect()
    torch.cuda.empty_cache()
    return file_name
