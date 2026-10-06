/*
 * ADAPTATEUR FORAGE (DRILLING-GE) — connexion unique (SSO) depuis le portail.
 *
 * À déposer dans le dépôt DRILLING-GE (ex: ./ge-sso.js) et à monter dans
 * server.js (voir adapters/forage/server-snippet.txt).
 *
 * Il ajoute la route GET /sso?token=... :
 *   - vérifie le jeton signé par le portail (secret PARTAGÉ SSO_SHARED_SECRET),
 *   - contrôle qu'il est bien destiné à "forage" et qu'il n'a jamais servi,
 *   - retrouve le compte dans la base Forage (username + enterpriseId),
 *   - pose le cookie forage_jwt habituel de l'app (via signUserToken),
 *   - pose un cookie lisible ge_switchbar pour la barre de bascule,
 *   - redirige vers l'application.
 *
 * Aucune logique métier de l'app n'est modifiée : on réutilise son propre
 * signUserToken et sa base. L'ancienne page de connexion reste disponible.
 */
const jwt = require('jsonwebtoken');
const { signUserToken } = require('./middleware/saas-auth');
const db = require('./db');

const SSO_SHARED_SECRET = process.env.SSO_SHARED_SECRET || '';
const PORTAIL_BASE_URL = process.env.PORTAIL_BASE_URL || '';
const COOKIE_SECURE = process.env.NODE_ENV === 'production';

// Anti-rejeu : jti déjà utilisés, gardés jusqu'à expiration (usage unique).
// NB : stockage en mémoire = suffisant pour 1 process. En multi-process,
// remplacer par une table SQLite ou Redis partagé.
const usedJti = new Map();
function rememberJti(jti, expSeconds) {
    usedJti.set(jti, expSeconds * 1000);
    if (usedJti.size > 5000) {
        const now = Date.now();
        for (const [k, v] of usedJti) if (v < now) usedJti.delete(k);
    }
}
function jtiAlreadyUsed(jti) {
    const exp = usedJti.get(jti);
    if (!exp) return false;
    if (exp < Date.now()) { usedJti.delete(jti); return false; }
    return true;
}

function registerSso(app) {
    app.get('/sso', (req, res) => {
        const token = req.query.token;
        if (!token) return res.status(400).send('Jeton manquant.');
        if (!SSO_SHARED_SECRET) return res.status(500).send('SSO non configuré (SSO_SHARED_SECRET).');

        let payload;
        try {
            payload = jwt.verify(token, SSO_SHARED_SECRET, {
                algorithms: ['HS256'],
                audience: 'forage',
                issuer: 'portail-ge',
            });
        } catch (e) {
            return res.status(401).send('Jeton invalide ou expiré.');
        }

        if (!payload.jti || jtiAlreadyUsed(payload.jti)) {
            return res.status(401).send('Jeton déjà utilisé.');
        }
        rememberJti(payload.jti, payload.exp);

        const username = String(payload.sub || '');
        const enterpriseId = payload.ent;
        if (!username || enterpriseId == null) {
            return res.status(400).send('Jeton incomplet.');
        }

        // Retrouver le compte dans la base Forage.
        db.get(
            'SELECT * FROM users WHERE username = ? AND enterpriseId = ?',
            [username, enterpriseId],
            (err, user) => {
                if (err) return res.status(500).send('Erreur base.');
                if (!user) return res.status(403).send('Compte Forage introuvable pour cette entreprise.');

                // Cookie de session habituel de l'app.
                const appToken = signUserToken(user, {
                    isSuperAdmin: false,
                    isPlatformOwner: false,
                    deploymentMode: process.env.DEPLOYMENT_MODE || 'dedicated',
                });
                res.cookie('forage_jwt', appToken, {
                    httpOnly: true,
                    sameSite: 'lax',
                    secure: COOKIE_SECURE,
                    maxAge: 7 * 24 * 3600 * 1000,
                });

                // Cookie lisible par la barre de bascule (non httpOnly).
                const sb = {
                    portal: payload.portal || PORTAIL_BASE_URL,
                    current: 'forage',
                    modules: Array.isArray(payload.mods) ? payload.mods : ['forage'],
                    enterprise: payload.name || '',
                };
                res.cookie('ge_switchbar', JSON.stringify(sb), {
                    httpOnly: false,
                    sameSite: 'lax',
                    secure: COOKIE_SECURE,
                    maxAge: 7 * 24 * 3600 * 1000,
                });

                return res.redirect('/');
            }
        );
    });
}

module.exports = { registerSso };
