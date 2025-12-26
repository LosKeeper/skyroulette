# backend/data.py
import discord


def candidate_members(guild):
    candidates = [
        m for m in guild.members
        if (
            not m.bot
            and m.status != discord.Status.offline
            and m != guild.owner
            and not m.guild_permissions.administrator
        )
    ]

    return candidates


def online_members(guild):
    online = [
        m for m in guild.members
        if (
            not m.bot
            and m.status != discord.Status.offline
        )
    ]

    return online
