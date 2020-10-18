# -*- coding: utf-8 -*-

from typing import Callable
from datetime import datetime as dt, timedelta as td
import time
from cmyui import log, Ansi, _isdecimal
import bcrypt

import packets
from packets import ClientPacket, BanchoPacketReader  # convenience

from constants.types import osuTypes
from constants.mods import Mods
from constants import commands
from constants import regexes
from objects import glob
from objects.match import MatchTeamTypes, SlotStatus, Teams
from objects.player import Player, PresenceFilter, Action
from objects.beatmap import Beatmap
from constants.privileges import Privileges

glob.bancho_map = {}


def bancho_packet(packet: ClientPacket) -> Callable:
    def register_callback(callback: Callable) -> Callable:
        glob.bancho_map |= {packet: callback}
        return callback
    return register_callback

# packet id: 0


@bancho_packet(ClientPacket.CHANGE_ACTION)
async def readStatus(p: Player, pr: BanchoPacketReader) -> None:
    data = await pr.read(
        osuTypes.u8,  # actionType
        osuTypes.string,  # infotext
        osuTypes.string,  # beatmap md5
        osuTypes.u32,  # mods
        osuTypes.u8,  # gamemode
        osuTypes.i32  # beatmapid
    )

    p.status.update(*data)
    glob.players.enqueue(await packets.userStats(p))

# packet id: 1


@bancho_packet(ClientPacket.SEND_PUBLIC_MESSAGE)
async def sendMessage(p: Player, pr: BanchoPacketReader) -> None:
    if p.silenced:
        log(f'{p} sent a message while silenced.', Ansi.YELLOW)
        return

    # we don't need client & client_id from osu!
    _, msg, target, _ = await pr.read(osuTypes.message)

    if target == '#spectator':
        if p.spectating:
            # we are spectating someone
            spec_id = p.spectating.id
        elif p.spectators:
            # we are being spectated
            spec_id = p.id
        else:
            return

        t = glob.channels[f'spec_{spec_id}']
    elif target == '#multiplayer':
        if not p.match:
            # they're not in a match?
            return

        t = glob.channels[f'#multi_{p.match.id}']
    else:
        t = glob.channels[target]

    if not t:
        log(f'{p} wrote to non-existent {target}.', Ansi.YELLOW)
        return

    if not p.priv & t.write:
        log(f'{p} wrote to {target} with insufficient privileges.')
        return

    # limit message length to 2048 characters
    msg = f'{msg[:2045]}...' if msg[2048:] else msg

    cmd = msg.startswith(glob.config.command_prefix) \
        and await commands.process_commands(p, t, msg)

    if cmd:
        # a command was triggered.
        if cmd['public']:
            await t.send(p, msg)
            if 'resp' in cmd:
                await t.send(glob.bot, cmd['resp'])
        else:
            staff = glob.players.staff
            await t.send_selective(p, msg, staff - {p})
            if 'resp' in cmd:
                await t.send_selective(glob.bot, cmd['resp'], staff | {p})

    else:
        # no commands were triggered

        # check if the user is /np'ing a map.
        # even though this is a public channel,
        # we'll update the player's last np stored.
        if _match := regexes.now_playing.match(msg):
            # the player is /np'ing a map.
            # save it to their player instance
            # so we can use this elsewhere owo..
            p.last_np = await Beatmap.from_bid(int(_match['bid']))

        await t.send(p, msg)

    log(f'{p} @ {t}: {msg}', Ansi.CYAN, fd='.data/logs/chat.log')

# packet id: 2


@bancho_packet(ClientPacket.LOGOUT)
async def logout(p: Player, pr: BanchoPacketReader) -> None:
    pr.ignore(4)  # osu sends i32(0) every time..

    if (time.time() - p.login_time) < 2:
        # osu! has a weird tendency to log out immediately when
        # it logs in, then reconnects? not sure why..?
        return

    await p.logout()
    log(f'{p} logged out.', Ansi.LYELLOW)

# packet id: 3


@bancho_packet(ClientPacket.REQUEST_STATUS_UPDATE)
async def statsUpdateRequest(p: Player, pr: BanchoPacketReader) -> None:
    p.enqueue(await packets.userStats(p))

registration_msg = '\n'.join((
    "Hey! Welcome to [https://github.com/cmyui/gulag/ the gulag].",
    "",
    "Command help: !help",
    "If you have any questions or find any strange behaviour,",
    "please feel feel free to contact cmyui(#0425) directly!"
))
# no specific packet id, triggered when the
# client sends a request without an osu-token.


async def login(origin: bytes, ip: str) -> tuple[bytes, str]:
    # login is a bit special, we return the response bytes
    # and token in a tuple - we need both for our response.
    if len(s := origin.decode().split('\n')[:-1]) != 3:
        return

    if p := await glob.players.get_by_name(username := s[0]):
        if (time.time() - p.last_receive_time) > 10:
            # if the current player obj online hasn't
            # pinged the server in > 10 seconds, log
            # them out and login the new user.
            await p.logout()
        else:
            # the user is currently online, send back failure.
            data = await packets.userID(-1) + \
                await packets.notification('User already logged in.')

            return data, 'no'

    del p

    pw_hash = s[1].encode()

    if len(s := s[2].split('|')) != 5:
        return

    if not (r := regexes.osu_ver.match(s[0])):
        # invalid client version?
        return await packets.userID(-2), 'no'

    # parse their osu version into a datetime object.
    # this will be saved to `p.osu_ver` if login succeeds.
    osu_ver = dt.strptime(r['ver'], '%Y%m%d')

    if osu_ver < dt.now() - td(60):
        # the osu! client is older than 2 months old,
        # disallow login and force an update re-check.
        return (await packets.versionUpdateForced() +
                await packets.userID(-2)), 'no'

    if not _isdecimal(s[1], _negative=True):
        # utc-offset isn't a number (negative inclusive).
        return await packets.userID(-1), 'no'

    utc_offset = int(s[1])
    display_city = s[2] == '1'

    # Client hashes contain a few values useful to us.
    # [0]: md5(osu path)
    # [1]: adapters (network physical addresses delimited by '.')
    # [2]: md5(adapters)
    # [3]: md5(uniqueid) (osu! uninstall id)
    # [4]: md5(uniqueid2) (disk signature/serial num)
    client_hashes = s[3].split(':')[:-1]
    client_hashes.pop(1)  # no need for non-md5 adapters

    pm_private = s[4] == '1'

    p_row = await glob.db.fetch(
        'SELECT id, name, priv, pw_hash, silence_end '
        'FROM users WHERE name_safe = %s',
        [Player.make_safe(username)]
    )

    if not p_row:
        # no account by this name exists.
        return await packets.userID(-1), 'no'

    # get our bcrypt cache.
    bcrypt_cache = glob.cache['bcrypt']

    # their account exists in sql.
    # check their account status & credentials against db.

    if pw_hash in bcrypt_cache:  # ~0.01 ms
        # cache hit - this saves ~200ms on subsequent logins.
        if bcrypt_cache[pw_hash] != p_row['pw_hash']:
            # password wrong
            return await packets.userID(-1), 'no'

    else:
        # cache miss, their first login since the server started.
        if not bcrypt.checkpw(pw_hash, p_row['pw_hash'].encode()):
            return await packets.userID(-1), 'no'

        bcrypt_cache[pw_hash] = p_row['pw_hash']

    if not p_row['priv'] & Privileges.Normal:
        return await packets.userID(-3), 'no'

    """ handle client hashes """

    # insert new set/occurrence
    await glob.db.execute(
        'INSERT INTO client_hashes '
        'VALUES (%s, %s, %s, %s, %s, NOW(), 0) '
        'ON DUPLICATE KEY UPDATE '
        'occurrences = occurrences + 1, '
        'latest_time = NOW() ',
        [p_row['id'], *client_hashes]
    )

    # TODO: runningunderwine support

    # find any other users from any of the same hwid values.
    hwid_matches = await glob.db.fetchall(
        'SELECT u.`name`, u.`priv`, h.`occurrences` '
        'FROM `client_hashes` h '
        'LEFT JOIN `users` u ON h.`userid` = u.`id` '
        'WHERE h.`userid` != %s AND (h.`adapters` = %s '
        'OR h.`uninstall_id` = %s OR h.`disk_serial` = %s)',
        [p_row['id'], *client_hashes[1:]]
    )

    if hwid_matches:
        # we have other accounts with matching hashes

        # NOTE: this is an area i've seen a lot of implementations rush
        # through and poorly design; this section is CRITICAL for both
        # keeping multiaccounting down, but perhaps more importantly in
        # scenarios where multiple users are forced to use a single pc
        # (lan meetups, at a friends place, shared computer, etc.).
        # these scenarios are usually the ones where new players will
        # get invited to your server.. first impressions are important
        # and you don't want a ban and support ticket to be this users
        # first experience. :P

        # anyways yeah needless to say i'm gonna think about this one

        if not p_row['priv'] & Privileges.Verified:
            # this player is not verified yet, this is their first
            # time connecting in-game and submitting their hwid set.
            # we will not allow any banned matches; if there are any,
            # then ask the user to contact staff and resolve manually.
            if not all(x['priv'] & Privileges.Normal for x in hwid_matches):
                return (await packets.notification('Please contact staff directly '
                                                   'to create an account.') +
                        await packets.userID(-1)), 'no'

        else:
            # player is verified
            # TODO: add discord webhooks to cmyui_pkg, it would be a
            # perfect addition here.. will have to think about how
            # to organize it in config tho :o
            pass

    if not p_row['priv'] & Privileges.Verified:
        # verify the account if it's made it this far
        p_row['priv'] |= int(Privileges.Verified)

        await glob.db.execute(
            'UPDATE users SET priv = priv | %s WHERE id = %s',
            [p_row['priv'], p_row['id']]
        )

    p_row |= {
        'utc_offset': utc_offset,
        'pm_private': pm_private,
        'osu_ver': osu_ver
    }

    p = Player(**p_row)

    data = bytearray(
        await packets.userID(p.id) +
        await packets.protocolVersion(19) +
        await packets.banchoPrivileges(p.bancho_priv) +
        await packets.notification('Welcome back to the gulag!\n'
                                   f'Current build: {glob.version}') +

        # tells osu! to load channels from config, i believe?
        await packets.channelInfoEnd()
    )

    # channels
    for c in glob.channels:
        if not p.priv & c.read:
            continue  # no priv to read

        # autojoinable channels
        if c.auto_join and await p.join_channel(c):
            # NOTE: p.join_channel enqueues channelJoin, but
            # if we don't send this back in this specific request,
            # the client will attempt to join the channel again.
            data.extend(await packets.channelJoin(c.name))

        data.extend(await packets.channelInfo(*c.basic_info))

    # fetch some of the player's
    # information from sql to be cached.
    await p.stats_from_sql_full()
    await p.friends_from_sql()

    if glob.config.server_build:
        # update their country data with
        # the IP from the login request.
        await p.fetch_geoloc(ip)

    # update our new player's stats, and broadcast them.
    user_data = (
        await packets.userPresence(p) +
        await packets.userStats(p)
    )

    data.extend(user_data)

    # o for online, or other
    for o in glob.players:
        # enqueue us to them
        o.enqueue(user_data)

        # enqueue them to us.
        data.extend(
            await packets.userPresence(o) +
            await packets.userStats(o)
        )

    data.extend(
        await packets.mainMenuIcon() +
        await packets.friendsList(*p.friends) +
        await packets.silenceEnd(p.remaining_silence)
    )

    # thank u osu for doing this by username rather than id
    query = ('SELECT m.`msg`, m.`time`, m.`from_id`, '
             '(SELECT name FROM users WHERE id = m.`from_id`) AS `from`, '
             '(SELECT name FROM users WHERE id = m.`to_id`) AS `to` '
             'FROM `mail` m WHERE m.`to_id` = %s AND m.`read` = 0')

    # the player may have been sent mail while offline,
    # enqueue any messages from their respective authors.
    async for msg in glob.db.iterall(query, p.id):
        msg_time = dt.fromtimestamp(msg['time'])
        msg_ts = f'[{msg_time:%Y-%m-%d %H:%M:%S}] {msg["msg"]}'

        data.extend(await packets.sendMessage(
            msg['from'], msg_ts,
            msg['to'], msg['from_id']
        ))

    # add `p` to the global player list,
    # making them officially logged in.
    glob.players.add(p)

    log(f'{p} logged in.', Ansi.LCYAN)
    return bytes(data), p.token

# packet id: 16


@bancho_packet(ClientPacket.START_SPECTATING)
async def startSpectating(p: Player, pr: BanchoPacketReader) -> None:
    target_id, = await pr.read(osuTypes.i32)

    if not (host := await glob.players.get_by_id(target_id)):
        log(f'{p} tried to spectate nonexistant id {target_id}.', Ansi.YELLOW)
        return

    if c_host := p.spectating:
        await c_host.remove_spectator(p)

    await host.add_spectator(p)

# packet id: 17


@bancho_packet(ClientPacket.STOP_SPECTATING)
async def stopSpectating(p: Player, pr: BanchoPacketReader) -> None:
    host = p.spectating

    if not host:
        log(f"{p} tried to stop spectating when they're not..?", Ansi.LRED)
        return

    await host.remove_spectator(p)

# packet id: 18


@bancho_packet(ClientPacket.SPECTATE_FRAMES)
async def spectateFrames(p: Player, pr: BanchoPacketReader) -> None:
    # this runs very frequently during spectation,
    # so it's written to run pretty quick.

    # read the entire data of the packet, and ignore it internally
    data = await packets.spectateFrames(pr.data[:pr.length])
    pr.ignore_packet()

    # enqueue the data
    # to all spectators.
    for t in p.spectators:
        t.enqueue(data)

# packet id: 21


@bancho_packet(ClientPacket.CANT_SPECTATE)
async def cantSpectate(p: Player, pr: BanchoPacketReader) -> None:
    if not p.spectating:
        log(f"{p} sent can't spectate while not spectating?", Ansi.LRED)
        return

    data = await packets.spectatorCantSpectate(p.id)

    host = p.spectating
    host.enqueue(data)

    for t in host.spectators:
        t.enqueue(data)

# packet id: 25


@bancho_packet(ClientPacket.SEND_PRIVATE_MESSAGE)
async def sendPrivateMessage(p: Player, pr: BanchoPacketReader) -> None:
    if p.silenced:
        log(f'{p} tried to send a dm while silenced.', Ansi.YELLOW)
        return

    # we don't need client & client_id from osu!
    _, msg, target, _ = await pr.read(osuTypes.message)

    if not (t := await glob.players.get_by_name(target)):
        log(f'{p} tried to write to non-existant user {target}.', Ansi.YELLOW)
        return

    if t.pm_private and p.id not in t.friends:
        p.enqueue(await packets.userPMBlocked(target))
        log(f'{p} tried to message {t}, but they are blocking dms.')
        return

    if t.silenced:
        p.enqueue(await packets.targetSilenced(target))
        log(f'{p} tried to message {t}, but they are silenced.')
        return

    msg = f'{msg[:2045]}...' if msg[2048:] else msg
    client, client_id = p.name, p.id

    if t.status.action == Action.Afk and t.away_msg:
        # send away message if target is afk and has one set.
        p.enqueue(await packets.sendMessage(client, t.away_msg, target, client_id))

    if t.id == 1:
        # target is the bot, check if message is a command.
        cmd = msg.startswith(glob.config.command_prefix) \
            and await commands.process_commands(p, t, msg)

        if cmd and 'resp' in cmd:
            # command triggered and there is a response to send.
            p.enqueue(await packets.sendMessage(t.name, cmd['resp'], client, t.id))

        else:
            # no commands triggered.
            if match := regexes.now_playing.match(msg):
                # user is /np'ing a map.
                # save it to their player instance
                # so we can use this elsewhere owo..
                p.last_np = await Beatmap.from_bid(int(match['bid']))

                if p.last_np:
                    if match['mods']:
                        # [1:] to remove leading whitespace
                        mods = Mods.from_np(match['mods'][1:])
                    else:
                        mods = Mods.NOMOD

                    if mods not in p.last_np.pp_cache:
                        await p.last_np.cache_pp(mods)

                    # since this is a DM to the bot, we should
                    # send back a list of general PP values.
                    # TODO: !acc and !mods in commands to
                    #       modify these values :P
                    _msg = [p.last_np.embed]
                    if mods:
                        _msg.append(f'{mods!r}')

                    msg = f"{' '.join(_msg)}: " + ' | '.join(
                        f'{acc}%: {pp:.2f}pp'
                        for acc, pp in zip(
                            (90, 95, 98, 99, 100),
                            p.last_np.pp_cache[mods]
                        ))

                else:
                    msg = 'Could not find map.'

                p.enqueue(await packets.sendMessage(t.name, msg, client, t.id))

    else:
        # target is not aika, send the message normally
        t.enqueue(await packets.sendMessage(client, msg, target, client_id))

        # insert mail into db,
        # marked as unread.
        await glob.db.execute(
            'INSERT INTO `mail` (`from_id`, `to_id`, `msg`, `time`) '
            'VALUES (%s, %s, %s, UNIX_TIMESTAMP())',
            [p.id, t.id, msg]
        )

    log(f'{p} @ {t}: {msg}', Ansi.CYAN, fd='.data/logs/chat.log')

# packet id: 29


@bancho_packet(ClientPacket.PART_LOBBY)
async def lobbyPart(p: Player, pr: BanchoPacketReader) -> None:
    p.in_lobby = False

# packet id: 30


@bancho_packet(ClientPacket.JOIN_LOBBY)
async def lobbyJoin(p: Player, pr: BanchoPacketReader) -> None:
    p.in_lobby = True

    for m in (_m for _m in glob.matches if _m):
        p.enqueue(await packets.newMatch(m))

# packet id: 31


@bancho_packet(ClientPacket.CREATE_MATCH)
async def matchCreate(p: Player, pr: BanchoPacketReader) -> None:
    m, = await pr.read(osuTypes.match)

    m.host = p
    await p.join_match(m, m.passwd)
    log(f'{p} created a new multiplayer match.')

# packet id: 32


@bancho_packet(ClientPacket.JOIN_MATCH)
async def matchJoin(p: Player, pr: BanchoPacketReader) -> None:
    m_id, passwd = await pr.read(osuTypes.i32, osuTypes.string)
    if 64 > m_id > 0:
        # make sure it's
        # a valid match id.
        return

    if not (m := glob.matches.get_by_id(m_id)):
        log(f'{p} tried to join a non-existant mp lobby?')
        return

    await p.join_match(m, passwd)

# packet id: 33


@bancho_packet(ClientPacket.PART_MATCH)
async def matchPart(p: Player, pr: BanchoPacketReader) -> None:
    await p.leave_match()

# packet id: 38


@bancho_packet(ClientPacket.MATCH_CHANGE_SLOT)
async def matchChangeSlot(p: Player, pr: BanchoPacketReader) -> None:
    if not (m := p.match):
        return

    # read new slot ID
    slot_id, = await pr.read(osuTypes.i32)
    if slot_id not in range(16):
        return

    if m.slots[slot_id].status & SlotStatus.has_player:
        log(f'{p} tried to switch to slot {slot_id} which has a player.')
        return

    # swap with current slot.
    s = m.get_slot(p)
    m.slots[slot_id].copy(s)
    s.reset()
    m.enqueue(await packets.updateMatch(m))

# packet id: 39


@bancho_packet(ClientPacket.MATCH_READY)
async def matchReady(p: Player, pr: BanchoPacketReader) -> None:
    if not (m := p.match):
        return

    m.get_slot(p).status = SlotStatus.ready
    m.enqueue(await packets.updateMatch(m))

# packet id: 40


@bancho_packet(ClientPacket.MATCH_LOCK)
async def matchLock(p: Player, pr: BanchoPacketReader) -> None:
    if not (m := p.match):
        return

    # read new slot ID
    slot_id, = await pr.read(osuTypes.i32)
    if slot_id not in range(16):
        return

    slot = m.slots[slot_id]

    if slot.status & SlotStatus.locked:
        slot.status = SlotStatus.open
    else:
        if slot.player:
            slot.reset()
        slot.status = SlotStatus.locked

    m.enqueue(await packets.updateMatch(m))

_head_vs_head = (MatchTeamTypes.head_to_head,
                 MatchTeamTypes.tag_coop)

# packet id: 41


@bancho_packet(ClientPacket.MATCH_CHANGE_SETTINGS)
async def matchChangeSettings(p: Player, pr: BanchoPacketReader) -> None:
    if not (m := p.match):
        return

    # read new match data
    new, = await pr.read(osuTypes.match)

    if new.freemods != m.freemods:
        # freemods status has been changed.
        if new.freemods:
            # switching to freemods.
            # central mods -> all players mods.
            for s in m.slots:
                if s.status & SlotStatus.has_player:
                    s.mods = m.mods & ~Mods.SPEED_CHANGING

            m.mods = m.mods & Mods.SPEED_CHANGING
        else:
            # switching to centralized mods.
            # host mods -> central mods.
            for s in m.slots:
                if s.player and s.player.id == m.host.id:
                    m.mods = s.mods | (m.mods & Mods.SPEED_CHANGING)
                    break

    if not new.bmap:
        # map being changed, unready players.
        for s in m.slots:
            if s.status & SlotStatus.ready:
                s.status = SlotStatus.not_ready
    elif not m.bmap:
        # new map has been chosen, send to match chat.
        await m.chat.send(glob.bot, f'Map selected: {new.bmap.embed}.')

    # copy basic match info into our match.
    m.bmap = new.bmap
    m.freemods = new.freemods
    m.mode = new.mode

    if m.team_type != new.team_type:
        # team type is changing, find the new appropriate default team.
        new_t = (Teams.red, Teams.neutral)[new.team_type in _head_vs_head]

        # change each active slots team to
        # fit the correspoding team type.
        for s in m.slots:
            if s.player:
                s.team = new_t

        # change the matches'.
        m.team_type = new.team_type

    m.match_scoring = new.match_scoring
    m.name = new.name

    m.enqueue(await packets.updateMatch(m))

# packet id: 44


@bancho_packet(ClientPacket.MATCH_START)
async def matchStart(p: Player, pr: BanchoPacketReader) -> None:
    if not (m := p.match):
        return

    for s in m.slots:
        if s.status & SlotStatus.ready:
            s.status = SlotStatus.playing

    m.in_progress = True
    m.enqueue(await packets.matchStart(m))

# packet id: 47


@bancho_packet(ClientPacket.MATCH_SCORE_UPDATE)
async def matchScoreUpdate(p: Player, pr: BanchoPacketReader) -> None:
    # this runs very frequently in matches,
    # so it's written to run pretty quick.

    if not (m := p.match):
        return

    # if scorev2 is enabled, read an extra 8 bytes.
    size = 37 if pr.data[28] else 29
    data = bytearray(pr.data[:size])  # hmmmm
    data[4] = m.get_slot_id(p)

    m.enqueue(b'0\x00\x00' + size.to_bytes(4, 'little') + data, lobby=False)
    pr.ignore(size)

# packet id: 49


@bancho_packet(ClientPacket.MATCH_COMPLETE)
async def matchComplete(p: Player, pr: BanchoPacketReader) -> None:
    if not (m := p.match):
        return

    m.get_slot(p).status = SlotStatus.complete

    all_completed = True

    for s in m.slots:
        if s.status & SlotStatus.playing:
            all_completed = False
            break

    if all_completed:
        m.in_progress = False
        m.enqueue(await packets.matchComplete())

        for s in m.slots:  # reset match statuses
            if s.status == SlotStatus.complete:
                s.status = SlotStatus.not_ready

# packet id: 51


@bancho_packet(ClientPacket.MATCH_CHANGE_MODS)
async def matchChangeMods(p: Player, pr: BanchoPacketReader) -> None:
    if not (m := p.match):
        return

    mods, = await pr.read(osuTypes.i32)

    if m.freemods:
        if p.id == m.host.id:
            # allow host to change speed-changing mods.
            m.mods = mods & Mods.SPEED_CHANGING

        # set slot mods
        m.get_slot(p).mods = mods & ~Mods.SPEED_CHANGING
    else:
        # not freemods, set match mods.
        m.mods = mods

    m.enqueue(await packets.updateMatch(m))

# packet id: 52


@bancho_packet(ClientPacket.MATCH_LOAD_COMPLETE)
async def matchLoadComplete(p: Player, pr: BanchoPacketReader) -> None:
    if not (m := p.match):
        return

    # ready up our player.
    m.get_slot(p).loaded = True

    # check if all players are ready.
    if not any(s.status & SlotStatus.playing and not s.loaded for s in m.slots):
        m.enqueue(await packets.matchAllPlayerLoaded(), lobby=False)

# packet id: 54


@bancho_packet(ClientPacket.MATCH_NO_BEATMAP)
async def matchNoBeatmap(p: Player, pr: BanchoPacketReader) -> None:
    if not (m := p.match):
        return

    m.get_slot(p).status = SlotStatus.no_map
    m.enqueue(await packets.updateMatch(m))

# packet id: 55


@bancho_packet(ClientPacket.MATCH_NOT_READY)
async def matchNotReady(p: Player, pr: BanchoPacketReader) -> None:
    if not (m := p.match):
        return

    m.get_slot(p).status = SlotStatus.not_ready
    m.enqueue(await packets.updateMatch(m), lobby=False)

# packet id: 56


@bancho_packet(ClientPacket.MATCH_FAILED)
async def matchFailed(p: Player, pr: BanchoPacketReader) -> None:
    if not (m := p.match):
        return

    # find the player's slot, and it into a playerFailed packet
    slot_id = m.get_slot_id(p)
    data = await packets.matchPlayerFailed(slot_id)

    # enqueue data to all players in the match
    m.enqueue(data)

# packet id: 59


@bancho_packet(ClientPacket.MATCH_HAS_BEATMAP)
async def matchHasBeatmap(p: Player, pr: BanchoPacketReader) -> None:
    if not (m := p.match):
        return

    m.get_slot(p).status = SlotStatus.not_ready
    m.enqueue(await packets.updateMatch(m))

# packet id: 60


@bancho_packet(ClientPacket.MATCH_SKIP_REQUEST)
async def matchSkipRequest(p: Player, pr: BanchoPacketReader) -> None:
    if not (m := p.match):
        return

    m.get_slot(p).skipped = True
    m.enqueue(await packets.matchPlayerSkipped(p.id))

    for s in m.slots:
        if s.status & SlotStatus.playing and not s.skipped:
            return

    # all users have skipped, enqueue a skip.
    m.enqueue(await packets.matchSkip(), lobby=False)

# packet id: 63


@bancho_packet(ClientPacket.CHANNEL_JOIN)
async def channelJoin(p: Player, pr: BanchoPacketReader) -> None:
    chan_name, = await pr.read(osuTypes.string)
    c = glob.channels[chan_name]

    if not c or not await p.join_channel(c):
        log(f'{p} failed to join {chan_name}.', Ansi.YELLOW)
        return

    # enqueue channelJoin to our player.
    p.enqueue(await packets.channelJoin(c.name))

# i wrote this and the server twin, ~2 weeks
# later the osu! team removed it and wrote
# /web/osu-getbeatmapinfo.php.. which to be
# fair is actually a lot nicer cuz its json
# but like cmon lol

# packet id: 68
# @bancho_packet(ClientPacket.BEATMAP_INFO_REQUEST)
# async def beatmapInfoRequest(p: Player, pr: PacketReader) -> None:
#    req: BeatmapInfoRequest
#    req, = await pr.read(osuTypes.mapInfoRequest)
#
#    info_list = []
#
#    # filenames
#    for fname in req.filenames:
#        # Attempt to regex pattern match the filename.
#        # If there is no match, simply ignore this map.
#        # XXX: Sometimes a map will be requested without a
#        # diff name, not really sure how to handle this? lol
#        if not (r := regexes.mapfile.match(fname)):
#            continue
#
#        res = await glob.db.fetch(
#            'SELECT id, set_id, status, md5 '
#            'FROM maps WHERE artist = %s AND '
#            'title = %s AND creator = %s AND '
#            'version = %s', [
#                r['artist'], r['title'],
#                r['creator'], r['version']
#            ]
#        )
#
#        if not res:
#            continue
#
#        to_osuapi_status = lambda s: {
#            0: 0,
#            2: 1,
#            3: 2,
#            4: 3,
#            5: 4
#        }[s]
#
#        info_list.append(BeatmapInfo(
#            0, res['id'], res['set_id'], 0,
#            to_osuapi_status(res['status']),
#
#            # TODO: best grade letter rank
#            # the order of these doesn't follow
#            # gamemode ids in osu! either.
#            # (std, ctb, taiko, mania)
#            Rank.N, Rank.N, Rank.N, Rank.N,
#
#            res['md5']
#        ))
#
#    # ids
#    for m in req.ids:
#        breakpoint()
#
#    p.enqueue(await packets.beatmapInfoReply(info_list))

# packet id: 70


@bancho_packet(ClientPacket.MATCH_TRANSFER_HOST)
async def matchTransferHost(p: Player, pr: BanchoPacketReader) -> None:
    if not (m := p.match):
        return

    # read new slot ID
    slot_id, = await pr.read(osuTypes.i32)
    if slot_id not in range(16):
        return

    if not (t := m[slot_id].player):
        log(f'{p} tried to transfer host to an empty slot?')
        return

    m.host = t
    m.host.enqueue(await packets.matchTransferHost())
    m.enqueue(await packets.updateMatch(m), lobby=False)

# packet id: 73


@bancho_packet(ClientPacket.FRIEND_ADD)
async def friendAdd(p: Player, pr: BanchoPacketReader) -> None:
    user_id, = await pr.read(osuTypes.i32)

    if not (t := await glob.players.get_by_id(user_id)):
        log(f'{t} tried to add a user who is not online! ({user_id})')
        return

    if t.id in (1, p.id):
        # trying to add the bot, or themselves.
        # these are already appended to the friends list
        # on login, so disallow the user from *actually*
        # editing these in sql.
        return

    await p.add_friend(t)

# packet id: 74


@bancho_packet(ClientPacket.FRIEND_REMOVE)
async def friendRemove(p: Player, pr: BanchoPacketReader) -> None:
    user_id, = await pr.read(osuTypes.i32)

    if not (t := await glob.players.get_by_id(user_id)):
        log(f'{t} tried to remove a user who is not online! ({user_id})')
        return

    if t.id in (1, p.id):
        # trying to remove the bot, or themselves.
        # these are already appended to the friends list
        # on login, so disallow the user from *actually*
        # editing these in sql.
        return

    await p.remove_friend(t)

# packet id: 77


@bancho_packet(ClientPacket.MATCH_CHANGE_TEAM)
async def matchChangeTeam(p: Player, pr: BanchoPacketReader) -> None:
    if not (m := p.match):
        return

    for s in m.slots:
        if p == s.player:
            s.team = Teams.blue if s.team != Teams.blue else Teams.red
            break
    else:
        log(f'{p} tried changing team outside of a match? (2)')
        return

    m.enqueue(await packets.updateMatch(m), lobby=False)

# packet id: 78


@bancho_packet(ClientPacket.CHANNEL_PART)
async def channelPart(p: Player, pr: BanchoPacketReader) -> None:
    chan, = await pr.read(osuTypes.string)

    if not chan:
        return

    if not (c := glob.channels[chan]):
        log(f'Failed to find channel {chan} that {p} attempted to leave.')
        return

    if p not in c:
        # user not in channel.
        return

    # leave the channel server-side.
    await p.leave_channel(c)

    # enqueue new channelinfo (playercount) to all players.
    glob.players.enqueue(await packets.channelInfo(*c.basic_info))

# packet id: 79


@bancho_packet(ClientPacket.RECEIVE_UPDATES)
async def receiveUpdates(p: Player, pr: BanchoPacketReader) -> None:
    val, = await pr.read(osuTypes.i32)

    if val not in range(3):
        log(f'{p} tried to set his presence filter to {val}?')
        return

    p.pres_filter = PresenceFilter(val)

# packet id: 82


@bancho_packet(ClientPacket.SET_AWAY_MESSAGE)
async def setAwayMessage(p: Player, pr: BanchoPacketReader) -> None:
    pr.ignore(3)  # why does first string send \x0b\x00?
    p.away_msg, = await pr.read(osuTypes.string)
    pr.ignore(4)

# packet id: 85


@bancho_packet(ClientPacket.USER_STATS_REQUEST)
async def statsRequest(p: Player, pr: BanchoPacketReader) -> None:
    if len(pr.data) < 6:
        return

    userIDs = await pr.read(osuTypes.i32_list)
    def is_online(o): return o in glob.players.ids and o != p.id

    for online in filter(is_online, userIDs):
        if t := await glob.players.get_by_id(online):
            p.enqueue(await packets.userStats(t))

# packet id: 87


@bancho_packet(ClientPacket.MATCH_INVITE)
async def matchInvite(p: Player, pr: BanchoPacketReader) -> None:
    if not p.match:
        pr.ignore(4)
        return

    user_id, = await pr.read(osuTypes.i32)
    if not (t := await glob.players.get_by_id(user_id)):
        log(f'{t} tried to invite a user who is not online! ({user_id})')
        return

    t.enqueue(await packets.matchInvite(p, t.name))
    log(f'{p} invited {t} to their match.')

# packet id: 90


@bancho_packet(ClientPacket.MATCH_CHANGE_PASSWORD)
async def matchChangePassword(p: Player, pr: BanchoPacketReader) -> None:
    if not (m := p.match):
        return

    # read new match data
    new, = await pr.read(osuTypes.match)

    m.passwd = new.passwd
    m.enqueue(await packets.updateMatch(m), lobby=False)

# packet id: 97


@bancho_packet(ClientPacket.USER_PRESENCE_REQUEST)
async def userPresenceRequest(p: Player, pr: BanchoPacketReader) -> None:
    for pid in await pr.read(osuTypes.i32_list):
        if t := await glob.players.get_by_id(pid):
            p.enqueue(await packets.userPresence(t))

# packet id: 98


@bancho_packet(ClientPacket.USER_PRESENCE_REQUEST_ALL)
async def userPresenceRequestAll(p: Player, pr: BanchoPacketReader) -> None:
    # XXX: this only sends when the client can see > 256 players,
    # so this probably won't have much use for private servers.

    # NOTE: i'm not exactly sure how bancho implements this and whether
    # i'm supposed to filter the users presences to send back with the
    # player's presence filter; i can add it in the future perhaps.
    for t in glob.players:
        if p != t:
            p.enqueue(await packets.userPresence(t))

# packet id: 99


@bancho_packet(ClientPacket.TOGGLE_BLOCK_NON_FRIEND_DMS)
async def toggleBlockingDMs(p: Player, pr: BanchoPacketReader) -> None:
    p.pm_private = (await pr.read(osuTypes.i32))[0] == 1

# some depreacted packets - no longer used in regular connections.
# XXX: perhaps these could be turned into decorators to allow
# for better specialization of params? perhaps prettier too :P


async def deprecated_packet(p: Player, pr: BanchoPacketReader) -> None:
    log(f'{p} sent deprecated packet {pr.current_packet!r}.', Ansi.LRED)

errorReport = bancho_packet(ClientPacket.ERROR_REPORT)(deprecated_packet)
beatmapInfoRequest = bancho_packet(
    ClientPacket.BEATMAP_INFO_REQUEST)(deprecated_packet)
