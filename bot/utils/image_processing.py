# bot/utils/image_processing.py
import io
import logging
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageSequence
import imageio.v3 as iio

# --- Constants ---
DISCORD_BANNER_WIDTH = 600
DISCORD_BANNER_HEIGHT = 240
AVATAR_TARGET_SIZE = 142
AVATAR_BORDER_WIDTH = 3
MISTY_LAYER_COLOR = (0, 0, 0, 40)
FONT_DIR = "fonts"
FONT_FALLBACK_PATHS = [
    os.path.join(FONT_DIR, "cute.ttf"),
    os.path.join(FONT_DIR, "setofont.ttf"),
]
USERNAME_FONT_SIZE = 65
DISCRIMINATOR_FONT_SIZE = 40
DATE_FONT_SIZE = 16
TEXT_COLOR = (255, 255, 255, 255)
LINE_SPACING = 15

# --- NEW COMPRESSION CONSTANTS ---
# For GIF: Control animation speed and frame count
GIF_MAX_FPS = 10  # Target maximum frames per second for output GIF (adjust as needed)
GIF_MIN_FRAME_DURATION_MS = int(
    700 / GIF_MAX_FPS
)  # Calculated duration in milliseconds
GIF_MAX_TOTAL_FRAMES = (
    80  # Maximum total frames for a GIF (prevents excessively long animations)
)

# For PNG: Ensure optimization is applied
PNG_OPTIMIZE = True


class ImageProcessor:
    def __init__(self):
        self.username_fonts = self._load_fonts(USERNAME_FONT_SIZE)
        self.discriminator_fonts = self._load_fonts(DISCRIMINATOR_FONT_SIZE)
        self.date_fonts = self._load_fonts(DATE_FONT_SIZE)

    def _load_fonts(self, size: int):
        fonts = []
        for font_path in FONT_FALLBACK_PATHS:
            try:
                font = ImageFont.truetype(font_path, size)
                fonts.append(font)
            except IOError:
                logging.error(
                    f"Warning: Could not load font from {font_path}. Skipping."
                )
            except Exception as e:
                logging.error(f"Error loading font {font_path}: {e}")
        if not fonts:
            logging.error("Error: No fonts loaded, falling back to default PIL font.")
            fonts.append(ImageFont.load_default())
        return fonts

    def _get_font_for_char(self, char: str, font_list: list[ImageFont.FreeTypeFont]):
        for font in font_list:
            if font.getmask(char).getbbox():
                return font
        return font_list[0]

    def _draw_text_with_fallback(
        self,
        draw: ImageDraw.ImageDraw,
        xy: tuple,
        text: str,
        font_list: list[ImageFont.FreeTypeFont],
        fill: tuple,
    ):
        x, y = xy
        for char in text:
            char_font = self._get_font_for_char(char, font_list)
            draw.text((x, y), char, font=char_font, fill=fill)
            char_width = char_font.getlength(char)
            x += char_width

    def round_avatar(
        self, avatar_img: Image.Image, size: int, border_width: int
    ) -> Image.Image:
        # Ensure avatar_img is RGBA before resizing
        if avatar_img.mode != "RGBA":
            avatar_img = avatar_img.convert("RGBA")

        avatar_resized = avatar_img.resize((size, size), Image.Resampling.LANCZOS)
        mask_size = size * 4
        mask = Image.new("L", (mask_size, mask_size), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, mask_size, mask_size), fill=255)
        mask = mask.resize((size, size), Image.Resampling.LANCZOS)

        rounded_avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        rounded_avatar.paste(avatar_resized, (0, 0), mask)

        # Shadow calculation and application (as per your original code)
        shadow_spread = border_width * 2.0
        shadow_blur_radius = border_width * 1.5
        shadow_offset_x = border_width * 0.75
        shadow_offset_y = border_width * 0.75
        shadow_alpha = 150

        canvas_size = int(size + shadow_spread * 2)
        composite_image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

        shadow_base_size = int(size + shadow_spread)
        shadow_source_canvas_size = int(shadow_base_size + shadow_blur_radius * 2)
        raw_shadow_source = Image.new(
            "RGBA", (shadow_source_canvas_size, shadow_source_canvas_size), (0, 0, 0, 0)
        )
        draw_raw_shadow = ImageDraw.Draw(raw_shadow_source)

        ellipse_x1 = (shadow_source_canvas_size - shadow_base_size) / 2
        ellipse_y1 = (shadow_source_canvas_size - shadow_base_size) / 2
        ellipse_x2 = ellipse_x1 + shadow_base_size
        ellipse_y2 = ellipse_y1 + shadow_base_size

        draw_raw_shadow.ellipse(
            (ellipse_x1, ellipse_y1, ellipse_x2, ellipse_y2),
            fill=(0, 0, 0, shadow_alpha),
        )

        shadow_blurred = raw_shadow_source.filter(
            ImageFilter.GaussianBlur(radius=shadow_blur_radius)
        )

        shadow_paste_x = int(
            (canvas_size - shadow_source_canvas_size) / 2 + shadow_offset_x
        )
        shadow_paste_y = int(
            (canvas_size - shadow_source_canvas_size) / 2 + shadow_offset_y
        )

        composite_image.paste(
            shadow_blurred, (shadow_paste_x, shadow_paste_y), shadow_blurred
        )
        avatar_x_pos = int((canvas_size - size) / 2)
        avatar_y_pos = int((canvas_size - size) / 2)
        composite_image.paste(
            rounded_avatar, (avatar_x_pos, avatar_y_pos), rounded_avatar
        )
        return composite_image

    def _create_inner_rounded_border_overlay(
        self,
        width: int,
        height: int,
        border_width: int,
        color: tuple,
        inner_corner_radius: int,
    ) -> Image.Image:
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        border_base = Image.new("RGBA", (width, height), color)
        inner_mask = Image.new("L", (width, height), 0)
        draw_inner_mask = ImageDraw.Draw(inner_mask)

        inner_x1 = border_width
        inner_y1 = border_width
        inner_x2 = width - border_width
        inner_y2 = height - border_width

        draw_inner_mask.rounded_rectangle(
            (inner_x1, inner_y1, inner_x2, inner_y2),
            radius=inner_corner_radius,
            fill=255,
        )
        border_base.paste((0, 0, 0, 0), (0, 0), inner_mask)
        overlay.paste(border_base, (0, 0), border_base)
        return overlay

    def _prepare_banner_frame(self, frame: Image.Image) -> Image.Image:
        # Ensure the frame is RGBA before processing
        if frame.mode != "RGBA":
            frame = frame.convert("RGBA")

        original_width, original_height = frame.size
        target_aspect_ratio = DISCORD_BANNER_WIDTH / DISCORD_BANNER_HEIGHT
        original_aspect_ratio = original_width / original_height

        if original_aspect_ratio > target_aspect_ratio:
            new_height = DISCORD_BANNER_HEIGHT
            new_width = int(original_width * (new_height / original_height))
            resized_frame = frame.resize(
                (new_width, new_height), Image.Resampling.LANCZOS
            )
            left = (new_width - DISCORD_BANNER_WIDTH) / 2
            top = 0
            right = (new_width + DISCORD_BANNER_WIDTH) / 2
            bottom = DISCORD_BANNER_HEIGHT
            cropped_frame = resized_frame.crop((left, top, right, bottom))
        else:
            new_width = DISCORD_BANNER_WIDTH
            new_height = int(original_height * (new_width / original_width))
            resized_frame = frame.resize(
                (new_width, new_height), Image.Resampling.LANCZOS
            )
            left = 0
            top = (new_height - DISCORD_BANNER_HEIGHT) / 2
            right = DISCORD_BANNER_WIDTH
            bottom = (new_height + DISCORD_BANNER_HEIGHT) / 2
            cropped_frame = resized_frame.crop((left, top, right, bottom))
        return cropped_frame  # Already converted to RGBA at the start of the function

    def _get_image_frames_and_durations(self, img: Image.Image):
        frames = []
        durations = []
        for f in ImageSequence.Iterator(img):
            # Ensure frame is RGBA and resize for GIF compression
            processed_frame = f.copy().convert("RGBA")
            # Apply banner dimensions to each frame to ensure consistent size
            processed_frame = self._prepare_banner_frame(processed_frame)
            frames.append(processed_frame)

            # --- Forced GIF Frame Duration ---
            # Prioritize GIF_MIN_FRAME_DURATION_MS to control overall FPS
            duration = f.info.get("duration", GIF_MIN_FRAME_DURATION_MS)
            try:
                duration = int(duration)
                if duration <= 0:
                    duration = GIF_MIN_FRAME_DURATION_MS
            except (ValueError, TypeError):
                duration = GIF_MIN_FRAME_DURATION_MS
            durations.append(
                max(duration, GIF_MIN_FRAME_DURATION_MS)
            )  # Ensure minimum duration
        return frames, durations

    def _draw_profile_text(
        self,
        draw: ImageDraw.ImageDraw,
        avatar_final_display_size: int,
        text_x: int,
        username_line_1: str,
        username_line_2: str,
        display_date_text: str,
    ):
        sample_font_username1 = (
            self.username_fonts[0] if self.username_fonts else ImageFont.load_default()
        )
        sample_font_username2 = (
            self.discriminator_fonts[0]
            if self.discriminator_fonts
            else ImageFont.load_default()
        )
        sample_font_date = (
            self.date_fonts[0] if self.date_fonts else ImageFont.load_default()
        )

        username_line_1_bbox = draw.textbbox(
            (0, 0), username_line_1, font=sample_font_username1
        )
        username_line_1_height = username_line_1_bbox[3] - username_line_1_bbox[1]

        username_line_2_bbox = draw.textbbox(
            (0, 0), username_line_2, font=sample_font_username2
        )
        username_line_2_height = username_line_2_bbox[3] - username_line_2_bbox[1]

        total_text_height = (
            username_line_1_height + username_line_2_height + LINE_SPACING
        )
        username_y_1 = (DISCORD_BANNER_HEIGHT - avatar_final_display_size) // 2 + (
            avatar_final_display_size - total_text_height
        ) // 2
        username_y_2 = username_y_1 + username_line_1_height + LINE_SPACING

        self._draw_text_with_fallback(
            draw,
            (text_x, username_y_1),
            username_line_1,
            self.username_fonts,
            TEXT_COLOR,
        )
        self._draw_text_with_fallback(
            draw,
            (text_x, username_y_2),
            username_line_2,
            self.discriminator_fonts,
            TEXT_COLOR,
        )

        date_text_bbox = draw.textbbox((0, 0), display_date_text, font=sample_font_date)
        date_width = date_text_bbox[2] - date_text_bbox[0]
        date_height = date_text_bbox[3] - date_text_bbox[1]
        date_x = DISCORD_BANNER_WIDTH - date_width - 15
        date_y = DISCORD_BANNER_HEIGHT - date_height - 15
        self._draw_text_with_fallback(
            draw, (date_x, date_y), display_date_text, self.date_fonts, TEXT_COLOR
        )

    def process_image_sync(
        self,
        banner_data: io.BytesIO,
        avatar_data: io.BytesIO,
        target_user_display_name: str,
        target_user_name: str,
        target_user_discriminator: str,
        created_at_date_str: str,
        generate_gif: bool,
    ) -> io.BytesIO | None:
        try:
            banner_img = Image.open(banner_data)
            avatar_img_raw = Image.open(avatar_data)
            output_frames = []
            frame_durations = []

            banner_is_animated = (
                hasattr(banner_img, "is_animated") and banner_img.is_animated
            )
            avatar_is_animated = (
                hasattr(avatar_img_raw, "is_animated") and avatar_img_raw.is_animated
            )
            should_generate_gif = generate_gif and (
                banner_is_animated or avatar_is_animated
            )

            # Process a static version of the avatar to get its final display size
            # This is used for text positioning, regardless of whether a GIF is generated
            temp_processed_avatar = self.round_avatar(
                avatar_img_raw.copy(), AVATAR_TARGET_SIZE, AVATAR_BORDER_WIDTH
            )
            avatar_final_display_size = temp_processed_avatar.width

            misty_layer = Image.new(
                "RGBA", (DISCORD_BANNER_WIDTH, DISCORD_BANNER_HEIGHT), MISTY_LAYER_COLOR
            )

            username_line_1 = target_user_display_name
            username_line_2 = (
                f"@{target_user_name}"
                if target_user_discriminator == "0"
                else f"#{target_user_discriminator}"
            )
            display_date_text = created_at_date_str

            banner_border_width = 6
            banner_border_color = (0, 0, 0, 100)
            banner_inner_corner_radius = 20

            border_overlay = self._create_inner_rounded_border_overlay(
                DISCORD_BANNER_WIDTH,
                DISCORD_BANNER_HEIGHT,
                banner_border_width,
                banner_border_color,
                banner_inner_corner_radius,
            )

            if should_generate_gif:
                logging.info(
                    f"Generating animated profile image with max FPS: {GIF_MAX_FPS}, max frames: {GIF_MAX_TOTAL_FRAMES}"
                )
                banner_frames_processed, _ = self._get_image_frames_and_durations(
                    banner_img
                )  # Banner frames are already resized within this function now
                avatar_frames_raw, _ = self._get_image_frames_and_durations(
                    avatar_img_raw
                )  # Avatar frames are already resized within this function now
                avatar_frames_processed = [
                    self.round_avatar(f, AVATAR_TARGET_SIZE, AVATAR_BORDER_WIDTH)
                    for f in avatar_frames_raw
                ]

                # Determine the total number of frames for the GIF
                total_frames_to_process = max(
                    len(banner_frames_processed), len(avatar_frames_processed)
                )

                # Limit the total number of frames to prevent excessively large GIFs
                if total_frames_to_process > GIF_MAX_TOTAL_FRAMES:
                    logging.warning(
                        f"GIF frame count ({total_frames_to_process}) exceeds MAX_TOTAL_FRAMES ({GIF_MAX_TOTAL_FRAMES}). Truncating GIF."
                    )
                    total_frames_to_process = GIF_MAX_TOTAL_FRAMES

                for i in range(total_frames_to_process):
                    current_banner_frame = banner_frames_processed[
                        i % len(banner_frames_processed)
                    ]
                    current_avatar_frame = avatar_frames_processed[
                        i % len(avatar_frames_processed)
                    ]

                    # Start with the prepared banner frame
                    composite_frame = current_banner_frame.copy()
                    composite_frame.paste(misty_layer, (0, 0), misty_layer)
                    composite_frame.paste(border_overlay, (0, 0), border_overlay)
                    draw = ImageDraw.Draw(composite_frame)

                    x_pos = 30
                    y_pos = (DISCORD_BANNER_HEIGHT - avatar_final_display_size) // 2
                    composite_frame.paste(
                        current_avatar_frame, (x_pos, y_pos), current_avatar_frame
                    )
                    text_x = x_pos + avatar_final_display_size + 20
                    self._draw_profile_text(
                        draw,
                        avatar_final_display_size,
                        text_x,
                        username_line_1,
                        username_line_2,
                        display_date_text,
                    )
                    output_frames.append(composite_frame)
                    # Use the fixed minimum duration for all frames
                    frame_durations.append(GIF_MIN_FRAME_DURATION_MS)

                if output_frames:
                    output_buffer = io.BytesIO()
                    try:
                        # Use imageio.v3.imwrite for GIF.
                        # Setting `fps` directly might be easier than `duration` for forced rate.
                        # `palettesize` is already limited.
                        # `optimize=True` for PIL internal optimization (if applicable through imageio).
                        iio.imwrite(
                            output_buffer,
                            [
                                f.convert("RGB") for f in output_frames
                            ],  # imageio needs RGB for GIFs
                            format="GIF",
                            loop=0,  # Loop infinitely
                            fps=GIF_MAX_FPS,  # Force max FPS
                            # palettesize=64, # Your existing setting, keep it
                            # subrectangles=True, # Potentially useful for smaller GIFs, but can be slow
                            # optimize=True # Not a direct imwrite parameter for GIF, but handled by fps/palettesize
                        )
                        output_buffer.seek(0)
                        return output_buffer
                    except Exception as e:
                        logging.error(f"Error saving GIF: {e}", exc_info=True)
                        logging.warning(
                            "Falling back to static image due to GIF saving error."
                        )
                        should_generate_gif = False  # Force static for the next step (if this fails, it will attempt PNG)
                else:
                    logging.warning(
                        "No GIF frames generated. Falling back to static image."
                    )
                    should_generate_gif = False  # Fallback to static if no frames

            # --- Static Image Handling (PNG) ---
            if (
                not should_generate_gif
            ):  # This path is taken if GIF is disabled or failed
                logging.info("Generating static profile image.")

                # Ensure banner is processed for static display
                banner_img_final = self._prepare_banner_frame(banner_img)

                # Apply overlays
                composite_img = banner_img_final.copy()
                composite_img.paste(misty_layer, (0, 0), misty_layer)
                composite_img.paste(border_overlay, (0, 0), border_overlay)
                draw = ImageDraw.Draw(composite_img)

                # Process avatar for static display (ensure it's not animated if the source was)
                if avatar_is_animated:
                    avatar_img_raw.seek(0)  # Reset pointer for animated image
                    static_avatar_frame = avatar_img_raw.seek(
                        0
                    ) or avatar_img_raw.convert("RGBA")  # Get first frame as static
                    avatar_img_processed = self.round_avatar(
                        static_avatar_frame, AVATAR_TARGET_SIZE, AVATAR_BORDER_WIDTH
                    )
                else:
                    avatar_img_processed = self.round_avatar(
                        avatar_img_raw, AVATAR_TARGET_SIZE, AVATAR_BORDER_WIDTH
                    )

                x_pos = 30
                y_pos = (DISCORD_BANNER_HEIGHT - avatar_final_display_size) // 2
                composite_img.paste(
                    avatar_img_processed, (x_pos, y_pos), avatar_img_processed
                )
                text_x = x_pos + avatar_final_display_size + 20
                self._draw_profile_text(
                    draw,
                    avatar_final_display_size,
                    text_x,
                    username_line_1,
                    username_line_2,
                    display_date_text,
                )
                output_buffer = io.BytesIO()
                # --- FORCED PNG COMPRESSION ---
                composite_img.save(output_buffer, format="PNG", optimize=PNG_OPTIMIZE)
                output_buffer.seek(0)
                return output_buffer

            return None  # Should only be reached if both GIF and PNG generation failed or were skipped

        except Exception as e:
            logging.error(
                f"Error in process_image_sync: {e}", exc_info=True
            )  # Use exc_info=True for full traceback
            return None
