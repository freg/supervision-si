// si-veille (#845) : icône dans la barre du haut -- état de la chaîne, dernière alerte, maillons, alertes récentes,
// journal et passage immédiat. Lit ~/.local/state/si-veille/etat.json écrit par le service si-veille.
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {resume} from './lib.js';

const DOSSIER = GLib.build_filenamev([GLib.get_user_state_dir(), 'si-veille']);
const ETAT = GLib.build_filenamev([DOSSIER, 'etat.json']);
const JOURNAL = GLib.build_filenamev([DOSSIER, 'journal.log']);
const COMMANDE = GLib.build_filenamev([GLib.get_home_dir(), '.local', 'bin', 'si-veille']);
const ICONES = {ok: 'security-high-symbolic', doute: 'security-medium-symbolic', panne: 'dialog-warning-symbolic',
    ancien: 'dialog-question-symbolic', absent: 'dialog-question-symbolic'};

function lire(chemin) {
    try {
        const [ok, octets] = GLib.file_get_contents(chemin);
        return ok ? new TextDecoder().decode(octets) : null;
    } catch (e) {
        return null;
    }
}

function ligne(texte) {
    return new PopupMenu.PopupMenuItem(texte, {reactive: false});
}

export default class SiVeille extends Extension {
    enable() {
        this._btn = new PanelMenu.Button(0.5, 'si-veille');
        const boite = new St.BoxLayout({style_class: 'si-veille-boite'});
        this._icone = new St.Icon({icon_name: ICONES.absent, style_class: 'system-status-icon'});
        this._label = new St.Label({text: '', y_align: Clutter.ActorAlign.CENTER, style_class: 'si-veille-texte'});
        boite.add_child(this._icone);
        boite.add_child(this._label);
        this._btn.add_child(boite);
        this._titre = ligne('');
        this._derniere = ligne('');
        this._btn.menu.addMenuItem(this._titre);
        this._btn.menu.addMenuItem(this._derniere);
        this._maillons = new PopupMenu.PopupSubMenuMenuItem('Maillons');
        this._alertes = new PopupMenu.PopupSubMenuMenuItem('Alertes récentes');
        this._btn.menu.addMenuItem(this._maillons);
        this._groupes = new PopupMenu.PopupMenuSection();     // veilles d'un hub (ex. réseau d'un site), une rubrique chacune
        this._btn.menu.addMenuItem(this._groupes);
        this._btn.menu.addMenuItem(this._alertes);
        this._btn.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        const journal = new PopupMenu.PopupMenuItem('Ouvrir le journal');
        journal.connect('activate', () => Gio.AppInfo.launch_default_for_uri(GLib.filename_to_uri(JOURNAL, null), null));
        const passer = new PopupMenu.PopupMenuItem('Vérifier maintenant');
        passer.connect('activate', () => {
            try {
                const p = Gio.Subprocess.new([COMMANDE, '--une-fois'], Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE);
                p.wait_async(null, () => this._maj());
            } catch (e) {
                logError(e, 'si-veille');
            }
        });
        this._btn.menu.addMenuItem(journal);
        this._btn.menu.addMenuItem(passer);
        this._btn.menu.connect('open-state-changed', (_m, ouvert) => { if (ouvert) this._maj(); });
        Main.panel.addToStatusArea(this.uuid, this._btn, 2, 'center');
        this._maj();
        this._minuteur = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 20, () => {
            this._maj();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _maj() {
        let e = null;
        try {
            e = JSON.parse(lire(ETAT) || 'null');
        } catch (x) {
            e = null;
        }
        const r = resume(e, Date.now() / 1000);
        this._icone.icon_name = ICONES[r.etat] || ICONES.absent;
        this._label.text = r.texte;
        for (const c of Object.keys(ICONES))
            this._btn.remove_style_class_name('si-veille-' + c);
        this._btn.add_style_class_name('si-veille-' + r.etat);
        this._titre.label.text = r.titre;
        this._derniere.label.text = r.derniere ? 'Dernière alerte : ' + r.derniere : 'Aucune alerte enregistrée';
        this._maillons.menu.removeAll();
        for (const m of r.maillons)
            this._maillons.menu.addMenuItem(ligne(m));
        this._groupes.removeAll();
        for (const g of r.groupes || []) {
            const sm = new PopupMenu.PopupSubMenuMenuItem(g.titre);
            for (const l of g.lignes)
                sm.menu.addMenuItem(ligne(l));
            this._groupes.addMenuItem(sm);
        }
        this._alertes.menu.removeAll();
        for (const a of r.alertes.length ? r.alertes : ['aucune'])
            this._alertes.menu.addMenuItem(ligne(a));
    }

    disable() {
        if (this._minuteur)
            GLib.source_remove(this._minuteur);
        this._minuteur = null;
        this._btn?.destroy();
        this._btn = this._icone = this._label = this._titre = this._derniere = this._maillons = this._alertes = this._groupes = null;
    }
}
