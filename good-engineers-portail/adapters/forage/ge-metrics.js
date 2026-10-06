/*
 * ADAPTATEUR FORAGE (DRILLING-GE) — API de métriques pour le rapport consolidé.
 *
 * À déposer dans DRILLING-GE (ex: ./ge-metrics.js) et à monter dans server.js
 * (voir server-snippet.txt). Deux routes, protégées par la clé de service
 * SERVICE_API_KEY (en-tête X-Service-Key) :
 *
 *   GET  /api/service/metrics?enterpriseId=..&start=YYYY-MM-DD&end=YYYY-MM-DD
 *        -> métriques forage de l'entreprise sur la période.
 *   POST /api/service/module-state   { enterpriseId, active }
 *        -> active / désactive l'entreprise (appelé quand on coche/décoche
 *           le module Forage dans le portail).
 *
 * Les données de forage sont rattachées à l'entreprise VIA LA FOREUSE :
 * dailyDataRecords.machineId -> drills.id -> drills.enterpriseId.
 */
const db = require('./db');
const bcrypt = require('bcryptjs');

const SERVICE_API_KEY = process.env.SERVICE_API_KEY || '';

function requireServiceKey(req, res, next) {
    if (!SERVICE_API_KEY) return res.status(500).json({ error: 'SERVICE_API_KEY non configurée' });
    if ((req.headers['x-service-key'] || '') !== SERVICE_API_KEY) {
        return res.status(401).json({ error: 'Clé de service invalide' });
    }
    next();
}

function registerMetrics(app) {
    // ---- Métriques ------------------------------------------------------
    app.get('/api/service/metrics', requireServiceKey, (req, res) => {
        const enterpriseId = parseInt(req.query.enterpriseId, 10);
        const start = String(req.query.start || '');
        const end = String(req.query.end || '');
        if (!enterpriseId || !start || !end) {
            return res.status(400).json({ error: 'enterpriseId, start et end requis' });
        }

        const sql = `
            SELECT d.machineId AS engin,
                   COALESCE(SUM(CAST(json_extract(d.data,'$.metersDrilled') AS REAL)),0) AS metres,
                   AVG(CAST(json_extract(d.data,'$.rop') AS REAL)) AS rop,
                   COUNT(*) AS saisies
            FROM dailyDataRecords d
            JOIN drills dr ON dr.id = d.machineId
            WHERE dr.enterpriseId = ? AND d.date >= ? AND d.date <= ?
            GROUP BY d.machineId
            ORDER BY metres DESC`;

        db.all(sql, [enterpriseId, start, end], (err, rows) => {
            if (err) return res.status(500).json({ error: err.message });
            rows = rows || [];

            // Coût consommables (best effort — table daily_consumables si présente).
            consommablesCost(enterpriseId, start, end, (coutConso) => {
                // Effectif rattaché à l'entreprise.
                db.get('SELECT COUNT(*) AS n FROM employees WHERE enterpriseId = ?',
                    [enterpriseId], (e2, r2) => {
                        const effectif = (r2 && r2.n) || 0;
                        const parEngin = rows.map((r) => ({
                            engin: r.engin,
                            metres: round(r.metres, 1),
                            rop: round(r.rop, 2),
                            arrets: 0, // à relier à votre table d'arrêts de poste si besoin
                            consommables_cout: 0,
                        }));
                        const metresTotal = parEngin.reduce((s, r) => s + (r.metres || 0), 0);
                        res.json({
                            module: 'forage',
                            periode: { start, end },
                            par_engin: parEngin,
                            metres_total: round(metresTotal, 1),
                            consommables_cout: round(coutConso, 2),
                            // Le forage ne suit pas encore le carburant en litres
                            // (fuelPct = niveau de cuve, pas une consommation).
                            carburant_litres: 0,
                            cout_total: round(coutConso, 2),
                            effectif: effectif,
                        });
                    });
            });
        });
    });

    // ---- Création / mise à jour d'un compte (pilotée par le portail) ---
    app.post('/api/service/user', requireServiceKey, (req, res) => {
        const b = req.body || {};
        const enterpriseId = parseInt(b.enterpriseId, 10);
        const username = String(b.username || '').trim();
        const password = String(b.password || '');
        const role = String(b.role || 'foreur');
        const name = String(b.name || username);
        if (!enterpriseId || !username || !password) {
            return res.status(400).json({ error: 'enterpriseId, username et password requis' });
        }
        const hash = bcrypt.hashSync(password, 10);
        db.get('SELECT id FROM users WHERE LOWER(TRIM(username)) = LOWER(?)', [username], (err, row) => {
            if (err) return res.status(500).json({ error: err.message });
            if (row) {
                db.run(
                    'UPDATE users SET password = ?, passwordHash = ?, role = ?, enterpriseId = ? WHERE id = ?',
                    ['', hash, role, enterpriseId, row.id],
                    (e2) => e2 ? res.status(500).json({ error: e2.message })
                                : res.json({ ok: true, updated: true, username })
                );
            } else {
                db.run(
                    'INSERT INTO users (username, password, passwordHash, role, name, enterpriseId, restrictions, notes, email, siteIds) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    [username, '', hash, role, name, enterpriseId, '{}', '', '', '[]'],
                    function (e2) {
                        if (e2) return res.status(500).json({ error: e2.message });
                        res.json({ ok: true, created: true, id: this.lastID, username });
                    }
                );
            }
        });
    });

    // ---- (Dé)activation de l'entreprise --------------------------------
    app.post('/api/service/module-state', requireServiceKey, (req, res) => {
        const enterpriseId = parseInt((req.body || {}).enterpriseId, 10);
        const active = (req.body || {}).active ? 1 : 0;
        if (!enterpriseId) return res.status(400).json({ error: 'enterpriseId requis' });
        db.run(
            "UPDATE enterprises SET isActive = ?, subscriptionStatus = ?, updatedAt = CURRENT_TIMESTAMP WHERE id = ?",
            [active, active ? 'active' : 'suspended', enterpriseId],
            function (err) {
                if (err) return res.status(500).json({ error: err.message });
                res.json({ ok: true, enterpriseId, active: !!active });
            }
        );
    });
}

function consommablesCost(enterpriseId, start, end, cb) {
    // Tolérant : si la table n'existe pas, on renvoie 0 sans planter.
    const sql = `
        SELECT COALESCE(SUM(CAST(totalCost AS REAL)),0) AS cout
        FROM daily_consumables
        WHERE enterpriseId = ? AND date >= ? AND date <= ?`;
    db.all(sql, [enterpriseId, start, end], (err, rows) => {
        if (err || !rows || !rows.length) return cb(0);
        cb(rows[0].cout || 0);
    });
}

function round(v, n) {
    if (v == null || isNaN(v)) return 0;
    const p = Math.pow(10, n);
    return Math.round(v * p) / p;
}

module.exports = { registerMetrics };
