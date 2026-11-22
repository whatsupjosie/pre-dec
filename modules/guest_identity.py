"""Human visiting cards: own-copy keys, host-bound proof and governed admission.

No remote host is fetched. First contact needs the host owner's approval and key
comparison; a random historical PubCast ID is not a certificate of a real person.
Returning IDs are pinned to the first admitted key. Admission remains owned by
GovernanceEngine; this module owns only invitations, proofs and guest leases.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from typing import Literal
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .credentials import CredentialStore
from .governance import EntryStatus, GovernanceEngine
from .human_profiles import HumanProfileDetails, shared_about


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def decoded(value: str, length: int) -> bytes:
    try:
        raw = base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)
    except (ValueError, TypeError):
        raise ValueError('Invalid identity encoding') from None
    if len(raw) != length or encoded(raw) != value:
        raise ValueError('Invalid identity encoding')
    return raw


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class Challenge(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    version: Literal[1] = 1
    host_id: str = Field(pattern=r'^[0-9a-f]{32}$')
    origin: str = Field(max_length=2048)
    nonce: str = Field(pattern=r'^[A-Za-z0-9_-]{43}$')
    expires: int

    @field_validator('origin')
    @classmethod
    def origin_only(cls, value):
        parsed = urlsplit(value)
        try:
            port = parsed.port
        except ValueError:
            raise ValueError('Invalid host origin') from None
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.path or parsed.query or parsed.fragment
                or any(c.isspace() or ord(c) < 32 for c in value)):
            raise ValueError('Use a complete HTTP or HTTPS host origin without a path')
        return value


class VisitingCard(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    user_id: str = Field(pattern=r'^u_[0-9a-f]{20}$')
    username: str = Field(min_length=3, max_length=64, pattern=r'^[A-Za-z0-9_.-]+$')
    display_name: str = Field(min_length=1, max_length=80)
    public_key: str = Field(pattern=r'^[A-Za-z0-9_-]{43}$')
    details: HumanProfileDetails

    @model_validator(mode='after')
    def explicitly_shared(self):
        if set(self.details.about) - set(self.details.public_fields) or (self.details.about and not self.details.discoverable):
            raise ValueError('A visiting card may contain only explicitly shared profile fields')
        return self


class VisitingPayload(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    challenge: Challenge
    card: VisitingCard
    consents: dict[str, bool]


def sign_visit(vault: CredentialStore, profile: dict, challenge: dict, consents: dict) -> dict:
    challenge = Challenge.model_validate(challenge)
    if not time.time() < challenge.expires <= time.time() + 305:
        raise ValueError('The host challenge expired; request a new one')
    key = Ed25519PrivateKey.from_private_bytes(vault.identity_secret(
        profile['user_id'], lambda: Ed25519PrivateKey.generate().private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())))
    details = HumanProfileDetails.model_validate(profile['details'])
    about = shared_about(profile) if details.discoverable else {}
    card = {'user_id': profile['user_id'], 'username': profile['username'],
            'display_name': profile['display_name'] or profile['username'],
            'public_key': encoded(key.public_key().public_bytes_raw()),
            'details': {'discoverable': details.discoverable, 'public_fields': list(about),
                        'about': about, 'onboarding_complete': True}}
    payload = VisitingPayload.model_validate({'challenge': challenge.model_dump(), 'card': card, 'consents': consents}).model_dump()
    return {'payload': payload, 'signature': encoded(key.sign(canonical(payload)))}


class GuestAdmission:
    def __init__(self, governance: GovernanceEngine, active_production=lambda: None):
        self.governance = governance
        self.active_production = active_production
        self.path = governance._db_path
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS guest_host (singleton INTEGER PRIMARY KEY CHECK(singleton=1), host_id TEXT NOT NULL, locked INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS door_arrivals (
                    arrival_id TEXT PRIMARY KEY, ticket_hash TEXT NOT NULL UNIQUE, name TEXT NOT NULL, source_key TEXT NOT NULL,
                    created REAL NOT NULL, expires REAL NOT NULL, decision TEXT NOT NULL DEFAULT 'waiting',
                    invite_code TEXT
                );
                CREATE TABLE IF NOT EXISTS host_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, name TEXT NOT NULL,
                    user_id TEXT, room TEXT NOT NULL, detail TEXT NOT NULL, reference TEXT, created REAL NOT NULL,
                    acknowledged INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS host_event_reads (
                    event_id INTEGER NOT NULL REFERENCES host_events(event_id), user_id TEXT NOT NULL,
                    PRIMARY KEY(event_id,user_id)
                );
                CREATE TABLE IF NOT EXISTS guest_pass_sessions (
                    session_id TEXT PRIMARY KEY, production_id TEXT, expires REAL NOT NULL, ended INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS guest_session_passes (
                    pass_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES guest_pass_sessions(session_id),
                    ticket_hash TEXT NOT NULL UNIQUE, user_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                    issued_at REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS guest_welcome (singleton INTEGER PRIMARY KEY CHECK(singleton=1), event_description TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS guest_invites (code_hash TEXT PRIMARY KEY, room TEXT NOT NULL, expires REAL NOT NULL, max_uses INTEGER NOT NULL, uses INTEGER NOT NULL DEFAULT 0, revoked INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS guest_auto_invites (code_hash TEXT PRIMARY KEY REFERENCES guest_invites(code_hash));
                CREATE TABLE IF NOT EXISTS guest_challenges (nonce TEXT PRIMARY KEY, challenge_json TEXT NOT NULL, invite_hash TEXT NOT NULL, poll_hash TEXT NOT NULL UNIQUE, expires REAL NOT NULL, proof_hash TEXT, entry_id TEXT);
                CREATE TABLE IF NOT EXISTS guest_sessions (entry_id TEXT PRIMARY KEY REFERENCES waiting_entries(entry_id), poll_hash TEXT NOT NULL UNIQUE, user_id TEXT NOT NULL, card_json TEXT NOT NULL, public_key TEXT NOT NULL, expires REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS guest_pins (user_id TEXT PRIMARY KEY, public_key TEXT NOT NULL, admitted_at REAL NOT NULL);
            ''')
            db.execute('INSERT OR IGNORE INTO guest_host(singleton,host_id) VALUES(1,?)', (secrets.token_hex(16),))
            self.host_id = db.execute('SELECT host_id FROM guest_host WHERE singleton=1').fetchone()[0]

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def invite(self, room='studio', duration=3600, max_uses=1, returning_auto=False):
        if not isinstance(room, str) or not room or len(room) > 128:
            raise ValueError('Choose a valid room')
        if type(duration) is not int or not 60 <= duration <= 86400 or type(max_uses) is not int or not 1 <= max_uses <= 100:
            raise ValueError('Invites last one minute to one day, for one to one hundred admissions')
        if type(returning_auto) is not bool:
            raise ValueError('Choose whether a returning guest may pass automatically')
        code = secrets.token_urlsafe(24)
        with self.connect() as db:
            db.execute('INSERT INTO guest_invites(code_hash,room,expires,max_uses) VALUES(?,?,?,?)',
                       (digest(code), room, time.time() + duration, max_uses))
            if returning_auto:
                db.execute('INSERT INTO guest_auto_invites VALUES(?)', (digest(code),))
        return code

    @staticmethod
    def _record_event(db, kind, name, *, room='', user_id=None, detail='', reference=None):
        cursor = db.execute(
            'INSERT INTO host_events(kind,name,user_id,room,detail,reference,created) VALUES(?,?,?,?,?,?,?)',
            (kind, name, user_id, room, detail, reference, time.time()),
        )
        return cursor.lastrowid

    def add_host_event(self, kind, name, *, room, user_id, detail):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if kind == 'host_request':
                existing = db.execute("SELECT event_id FROM host_events WHERE kind=? AND user_id=? AND room=? "
                                      "AND acknowledged=0 ORDER BY event_id DESC LIMIT 1",
                                      (kind, user_id, room)).fetchone()
                if existing:
                    return existing['event_id']
            return self._record_event(db, kind, name, room=room, user_id=user_id, detail=detail)

    def host_events(self, user_id, before=None, limit=100):
        with self.connect() as db:
            rows = db.execute(
                'SELECT e.*, r.user_id IS NOT NULL AS seen FROM host_events e '
                'LEFT JOIN host_event_reads r ON e.event_id=r.event_id AND r.user_id=? '
                'WHERE (? IS NULL OR e.event_id < ?) ORDER BY e.event_id DESC LIMIT ?',
                (user_id, before, before, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def acknowledge_event(self, event_id, user_id):
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM host_events WHERE event_id=?', (event_id,)).fetchone():
                return False
            db.execute('INSERT OR IGNORE INTO host_event_reads VALUES(?,?)', (event_id, user_id))
            return True

    def acknowledge_visit(self, entry_id):
        with self.connect() as db:
            db.execute("UPDATE host_events SET acknowledged=1 WHERE kind='verified_arrival' AND reference=?", (entry_id,))

    def knock(self, name, ticket, source):
        if not isinstance(name, str) or not 2 <= len(name.strip()) <= 64 or not name.strip().isprintable():
            raise ValueError('Enter a screen name of 2 to 64 characters')
        if not isinstance(ticket, str) or not re.fullmatch(r'[a-f0-9]{64}', ticket):
            raise ValueError('Invalid waiting room ticket')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            now = time.time()
            db.execute('DELETE FROM door_arrivals WHERE expires<=?', (now,))
            existing = db.execute('SELECT arrival_id FROM door_arrivals WHERE ticket_hash=?',
                                  (digest(ticket),)).fetchone()
            if existing:
                return existing['arrival_id']
            source_key = digest(self.host_id + ':' + source)
            if db.execute("SELECT count(*) FROM door_arrivals WHERE source_key=? AND created>?",
                          (source_key, now - 120)).fetchone()[0] >= 8:
                raise ValueError('Too many arrivals from this connection. Try again shortly.')
            if db.execute("SELECT count(*) FROM door_arrivals WHERE decision='waiting'").fetchone()[0] >= 100:
                raise ValueError('The Airlock is busy. Try again shortly.')
            arrival_id = secrets.token_hex(12)
            db.execute('INSERT INTO door_arrivals(arrival_id,ticket_hash,name,source_key,created,expires) VALUES(?,?,?,?,?,?)',
                       (arrival_id, digest(ticket), name.strip(), source_key, now, now + 1800))
            self._record_event(db, 'arrival', name.strip(), room='airlock', reference=arrival_id)
            return arrival_id

    def arrival_status(self, ticket):
        if not isinstance(ticket, str) or not re.fullmatch(r'[a-f0-9]{64}', ticket):
            raise ValueError('Invalid waiting room ticket')
        with self.connect() as db:
            key = digest(ticket)
            passed = db.execute('''SELECT p.*, s.production_id,s.expires,s.ended
                                   FROM guest_session_passes p JOIN guest_pass_sessions s USING(session_id)
                                   WHERE p.ticket_hash=?''', (key,)).fetchone()
            if passed:
                return self._pass_status(passed)
            row = db.execute('SELECT decision,invite_code,expires FROM door_arrivals WHERE ticket_hash=?',
                             (key,)).fetchone()
        if not row or row['expires'] <= time.time():
            return {'status': 'expired'}
        return {'status': row['decision'], 'invite_code': row['invite_code']}

    def arrivals(self):
        with self.connect() as db:
            rows = db.execute("SELECT arrival_id,name,created FROM door_arrivals WHERE decision='waiting' "
                              'AND expires>? ORDER BY created', (time.time(),)).fetchall()
        return [dict(row) for row in rows]

    def decide_arrival(self, arrival_id, allow, actor):
        if type(allow) is not bool:
            raise ValueError('Choose whether to invite this visitor')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            now = time.time()
            row = db.execute("SELECT * FROM door_arrivals WHERE arrival_id=? AND decision='waiting' AND expires>?",
                             (arrival_id, now)).fetchone()
            if not row:
                raise ValueError('This visitor is no longer waiting')
            code = secrets.token_urlsafe(24) if allow else None
            if code:
                db.execute('INSERT INTO guest_invites(code_hash,room,expires,max_uses) VALUES(?,?,?,?)',
                           (digest(code), 'studio', now + 900, 1))
            status = 'invited' if allow else 'denied'
            db.execute('UPDATE door_arrivals SET decision=?,invite_code=?,expires=? WHERE arrival_id=?',
                       (status, code, now + 900, arrival_id))
            db.execute("UPDATE host_events SET acknowledged=1 WHERE kind='arrival' AND reference=?", (arrival_id,))
            self._record_event(db, 'door_decision', row['name'], room='airlock', detail=status, user_id=actor,
                               reference=arrival_id)
        return status

    def _pass_status(self, row):
        if (row['revoked'] or row['ended'] or row['expires'] <= time.time()
                or row['production_id'] != self.active_production()
                or self.governance.is_banned(row['user_id'])[0]):
            return {'status': 'expired'}
        return {'status': 'session_pass', 'entry_id': row['pass_id'], 'user_id': row['user_id'],
                'display_name': row['name'], 'issued_at': row['issued_at'], 'expires': row['expires']}

    @staticmethod
    def _pass_session(db, production_id, now):
        return db.execute('SELECT * FROM guest_pass_sessions WHERE ended=0 AND expires>? '
                          'AND production_id IS ? ORDER BY rowid DESC LIMIT 1', (now, production_id)).fetchone()

    def issue_session_pass(self, arrival_id, actor):
        """Permit this waiting browser to enter for one session without asserting consent."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            now = time.time()
            arrival = db.execute("SELECT * FROM door_arrivals WHERE arrival_id=? AND decision='waiting' AND expires>?",
                                 (arrival_id, now)).fetchone()
            if not arrival:
                raise ValueError('This visitor is no longer waiting')
            production_id = self.active_production()
            session = self._pass_session(db, production_id, now)
            if session is None:
                session_id = secrets.token_hex(16)
                db.execute('INSERT INTO guest_pass_sessions(session_id,production_id,expires) VALUES(?,?,?)',
                           (session_id, production_id, now + 8 * 3600))
            else:
                session_id = session['session_id']
            pass_id = 'pass_' + secrets.token_hex(12)
            user_id = 'u_' + secrets.token_hex(10)
            db.execute('INSERT INTO guest_session_passes(pass_id,session_id,ticket_hash,user_id,name,issued_at) '
                       'VALUES(?,?,?,?,?,?)', (pass_id, session_id, arrival['ticket_hash'], user_id, arrival['name'], now))
            db.execute("UPDATE door_arrivals SET decision='session_pass' WHERE arrival_id=?", (arrival_id,))
            db.execute("UPDATE host_events SET acknowledged=1 WHERE kind='arrival' AND reference=?", (arrival_id,))
            self._record_event(db, 'door_decision', arrival['name'], room='airlock', user_id=actor,
                               detail='Owner issued a session pass without contract signature', reference=pass_id)
            return pass_id

    def pass_session(self):
        with self.connect() as db:
            session = self._pass_session(db, self.active_production(), time.time())
            if not session:
                return {'passes': [], 'expires': None}
            rows = db.execute('SELECT pass_id,name,issued_at FROM guest_session_passes '
                              'WHERE session_id=? AND revoked=0 ORDER BY issued_at', (session['session_id'],)).fetchall()
        return {'passes': [dict(row) for row in rows], 'expires': session['expires']}

    def end_pass_session(self, actor):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            updated = db.execute('UPDATE guest_pass_sessions SET ended=1 WHERE ended=0').rowcount
            if updated:
                self._record_event(db, 'door_decision', 'Temporary guest passes', room='airlock',
                                   user_id=actor, detail='Owner ended the temporary-pass session')
        return bool(updated)

    def set_locked(self, locked: bool):
        if type(locked) is not bool:
            raise ValueError('Choose whether the door is locked')
        with self.connect() as db:
            db.execute('UPDATE guest_host SET locked=? WHERE singleton=1', (int(locked),))

    def settings(self):
        with self.connect() as db:
            row = db.execute('SELECT * FROM guest_host WHERE singleton=1').fetchone()
        return {'host_id': self.host_id, 'locked': bool(row['locked'])}

    def event_description(self):
        with self.connect() as db:
            row = db.execute('SELECT event_description FROM guest_welcome WHERE singleton=1').fetchone()
        return row['event_description'] if row else ''

    def set_event_description(self, description):
        if not isinstance(description, str) or len(description) > 1000:
            raise ValueError('Enter up to 1,000 characters for tonight’s event')
        description = description.strip()
        with self.connect() as db:
            db.execute('''INSERT INTO guest_welcome(singleton,event_description) VALUES(1,?)
                          ON CONFLICT(singleton) DO UPDATE SET event_description=excluded.event_description''',
                       (description,))
        return description

    @staticmethod
    def _invite(db, code_hash):
        invite = db.execute('SELECT * FROM guest_invites WHERE code_hash=?', (code_hash,)).fetchone()
        if not invite or invite['revoked'] or invite['expires'] <= time.time() or invite['uses'] >= invite['max_uses']:
            raise ValueError('Invitation is invalid, expired or already used')
        return invite

    def challenge(self, code: str, origin: str):
        nonce, poll = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        value = Challenge(host_id=self.host_id, origin=origin, nonce=nonce, expires=int(time.time()) + 300).model_dump()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self._invite(db, digest(code))
            db.execute('DELETE FROM guest_challenges WHERE expires<? AND entry_id IS NULL', (time.time(),))
            if db.execute('SELECT count(*) FROM guest_challenges WHERE expires>?', (time.time(),)).fetchone()[0] >= 1000:
                raise ValueError('The waiting room is busy; try again shortly')
            db.execute('INSERT INTO guest_challenges(nonce,challenge_json,invite_hash,poll_hash,expires) VALUES(?,?,?,?,?)',
                       (nonce, canonical(value).decode(), digest(code), digest(poll), value['expires']))
        return {'challenge': value, 'poll_token': poll}

    def submit(self, proof: dict, local_ids=()):
        if set(proof) != {'payload', 'signature'} or len(canonical(proof)) > 32000:
            raise ValueError('Invalid visiting proof')
        payload = VisitingPayload.model_validate(proof['payload']).model_dump()
        card, challenge = payload['card'], payload['challenge']
        if card['user_id'] in local_ids:
            raise ValueError('A visitor cannot claim a local account identity')
        try:
            Ed25519PublicKey.from_public_bytes(decoded(card['public_key'], 32)).verify(decoded(proof['signature'], 64), canonical(payload))
        except InvalidSignature:
            raise ValueError('The visiting signature is invalid') from None
        required = {'tos', 'recording', 'ai_disclosure', 'data_processing'}
        if any(payload['consents'].get(name) is not True for name in required):
            raise ValueError('Accept the required production consents before entering')
        proof_hash = hashlib.sha256(canonical(proof)).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            issued = db.execute('SELECT * FROM guest_challenges WHERE nonce=?', (challenge['nonce'],)).fetchone()
            if not issued or issued['challenge_json'] != canonical(challenge).decode() or issued['expires'] <= time.time():
                raise ValueError('The visiting challenge is invalid or expired')
            if issued['entry_id']:
                if issued['proof_hash'] != proof_hash:
                    raise ValueError('This challenge has already been used')
                return issued['entry_id']
            invite = self._invite(db, issued['invite_hash'])
            pinned = db.execute('SELECT public_key FROM guest_pins WHERE user_id=?', (card['user_id'],)).fetchone()
            if pinned and pinned[0] != card['public_key']:
                raise ValueError('This returning PubCast ID has a different identity key')
            entry = self.governance._insert_waiting_entry(db, card['user_id'], card['display_name'], invite['room'], payload['consents'])
            db.execute('UPDATE guest_invites SET uses=uses+1 WHERE code_hash=?', (issued['invite_hash'],))
            db.execute('UPDATE guest_challenges SET proof_hash=?,entry_id=? WHERE nonce=?', (proof_hash, entry.entry_id, challenge['nonce']))
            db.execute('INSERT INTO guest_sessions(entry_id,poll_hash,user_id,card_json,public_key,expires) VALUES(?,?,?,?,?,?)',
                       (entry.entry_id, issued['poll_hash'], card['user_id'], canonical(card).decode(), card['public_key'], time.time() + 8 * 3600))
            unlocked = not db.execute('SELECT locked FROM guest_host WHERE singleton=1').fetchone()[0]
            security_pass = pinned and db.execute('SELECT 1 FROM guest_auto_invites WHERE code_hash=?',
                                                  (issued['invite_hash'],)).fetchone()
            auto = bool(unlocked or security_pass)
            self._record_event(db, 'verified_arrival', card['display_name'], room=invite['room'],
                               user_id=card['user_id'], reference=entry.entry_id,
                               detail='Verified invitation' if auto else 'Waiting for door staff')
        self.governance._audit('VERIFIED_ENTRY_REQUEST', card['user_id'], None, 'entry=' + entry.entry_id)
        if auto:
            self.governance.approve_entry(entry.entry_id, 'airlock_security' if security_pass else 'owner_unlocked_door')
            self.acknowledge_visit(entry.entry_id)
        return entry.entry_id

    def status(self, poll_token: str):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            session = db.execute('SELECT * FROM guest_sessions WHERE poll_hash=?', (digest(poll_token),)).fetchone()
            if not session:
                raise ValueError('No verified waiting request for this ticket')
            entry = self.governance.get_waiting_entry(session['entry_id'])
            result = {'entry_id': session['entry_id'], 'status': entry.status.value, 'user_id': session['user_id'], 'card_at': entry.requested_at}
            if session['revoked'] or session['expires'] <= time.time():
                result['status'] = 'expired'
            if result['status'] in {EntryStatus.APPROVED.value, EntryStatus.ENTERED.value}:
                pinned = db.execute('SELECT public_key FROM guest_pins WHERE user_id=?', (session['user_id'],)).fetchone()
                if pinned and pinned[0] != session['public_key']:
                    raise ValueError('This PubCast ID was admitted with a different key')
                db.execute('INSERT OR IGNORE INTO guest_pins VALUES(?,?,?)', (session['user_id'], session['public_key'], time.time()))
                result.update(card=json.loads(session['card_json']), expires=session['expires'])
            return result

    def validate_claims(self, claims: dict) -> bool:
        if claims.get('guest_host') != self.host_id or claims.get('role') != 'guest':
            return False
        if self.governance.is_banned(claims.get('sub'))[0]:
            return False
        with self.connect() as db:
            entry = claims.get('guest_entry')
            if isinstance(entry, str) and entry.startswith('pass_'):
                passed = db.execute('''SELECT p.*,s.production_id,s.expires,s.ended
                                       FROM guest_session_passes p JOIN guest_pass_sessions s USING(session_id)
                                       WHERE p.pass_id=? AND p.user_id=?''', (entry, claims.get('sub'))).fetchone()
                return bool(passed and self._pass_status(passed)['status'] == 'session_pass')
            row = db.execute('''SELECT s.*, e.status FROM guest_sessions s JOIN waiting_entries e USING(entry_id)
                                JOIN guest_pins p ON p.user_id=s.user_id AND p.public_key=s.public_key
                                WHERE s.entry_id=?''', (claims.get('guest_entry'),)).fetchone()
        return bool(row and not row['revoked'] and row['expires'] > time.time()
                    and row['user_id'] == claims.get('sub') and row['status'] in {'approved', 'entered'})

    def revoke(self, entry_id: str):
        with self.connect() as db:
            if entry_id.startswith('pass_'):
                db.execute('UPDATE guest_session_passes SET revoked=1 WHERE pass_id=?', (entry_id,))
            else:
                db.execute('UPDATE guest_sessions SET revoked=1 WHERE entry_id=?', (entry_id,))

    def pending(self):
        with self.connect() as db:
            rows = db.execute('''SELECT s.entry_id,s.card_json,s.public_key,p.public_key AS pinned
                                 FROM guest_sessions s JOIN waiting_entries e USING(entry_id)
                                 LEFT JOIN guest_pins p ON p.user_id=s.user_id
                                 WHERE e.status='waiting' AND s.revoked=0 AND s.expires>?''', (time.time(),)).fetchall()
        return [dict(entry_id=row['entry_id'], card=json.loads(row['card_json']),
                     fingerprint=digest(row['public_key']), known_key=row['pinned'] == row['public_key']) for row in rows]
