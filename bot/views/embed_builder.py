import discord


def build_settings_embed(
    guild_name: str,
    auto_link_fix: bool,
    enabled_platforms: list[str],
    allowed_channels: list[int],
) -> discord.Embed:
    embed = discord.Embed(
        title=f"連結修正設定 - {guild_name}", color=discord.Color.blurple()
    )
    embed.add_field(
        name="自動修正", value="✅ 啟用" if auto_link_fix else "❌ 關閉", inline=False
    )
    embed.add_field(
        name="已啟用平台",
        value=", ".join(enabled_platforms) if enabled_platforms else "（無）",
        inline=False,
    )
    embed.add_field(
        name="授權頻道",
        value=", ".join(f"<#{ch_id}>" for ch_id in allowed_channels)
        if allowed_channels
        else "（無）",
        inline=False,
    )
    embed.set_footer(text="可透過下方元件調整設定")
    return embed
