// si-mailbox (#843) : icône + micro-statut « non lus · non lus du 1er filtre » à côté de la date (GNOME 45+).
// Lit seulement ~/.local/share/si-mailbox/compteurs.json (des nombres) écrit par l'agent si-mailbox de la session.
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {resume} from './lib.js';

const FICHIER = GLib.build_filenamev([GLib.get_user_data_dir(), 'si-mailbox', 'compteurs.json']);
const JETON = GLib.build_filenamev([GLib.get_user_config_dir(), 'si-mailbox', 'jeton']);

function lire(chemin) {
    try {
        const [ok, octets] = GLib.file_get_contents(chemin);
        return ok ? new TextDecoder().decode(octets) : null;
    } catch (e) {
        return null;
    }
}

export default class SiMailbox extends Extension {
    enable() {
        this._btn = new PanelMenu.Button(0.5, 'si-mailbox');
        const boite = new St.BoxLayout({style_class: 'si-mailbox-boite'});
        this._icone = new St.Icon({icon_name: 'mail-read-symbolic', style_class: 'system-status-icon'});
        this._label = new St.Label({text: '…', y_align: Clutter.ActorAlign.CENTER, style_class: 'si-mailbox-texte'});
        boite.add_child(this._icone);
        boite.add_child(this._label);
        this._btn.add_child(boite);
        this._section = new PopupMenu.PopupMenuSection();
        this._btn.menu.addMenuItem(this._section);
        this._btn.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        const ouvrir = new PopupMenu.PopupMenuItem('Ouvrir si-mailbox');
        ouvrir.connect('activate', () => {
            const j = (lire(JETON) || '').trim();
            Gio.AppInfo.launch_default_for_uri(`http://127.0.0.1:8095/?jeton=${encodeURIComponent(j)}`, null);
        });
        this._btn.menu.addMenuItem(ouvrir);
        this._btn.menu.connect('open-state-changed', (_m, ouvert) => { if (ouvert) this._maj(); });
        Main.panel.addToStatusArea(this.uuid, this._btn, 1, 'center');   // juste après la date
        this._maj();
        this._minuteur = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 20, () => {
            this._maj();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _maj() {
        let d = null;
        try {
            d = JSON.parse(lire(FICHIER) || 'null');
        } catch (e) {
            d = null;
        }
        const r = resume(d, Date.now() / 1000);
        this._label.text = r.texte;
        this._icone.icon_name = r.etat === 'erreur' ? 'dialog-warning-symbolic' : (d && d.total > 0 ? 'mail-unread-symbolic' : 'mail-read-symbolic');
        for (const c of ['calme', 'non_lus', 'filtre', 'ancien', 'erreur', 'absent'])
            this._btn.remove_style_class_name('si-mailbox-' + c);
        this._btn.add_style_class_name('si-mailbox-' + r.etat);
        this._section.removeAll();
        for (const l of r.lignes)
            this._section.addMenuItem(new PopupMenu.PopupMenuItem(l, {reactive: false}));
    }

    disable() {
        if (this._minuteur)
            GLib.source_remove(this._minuteur);
        this._minuteur = null;
        this._btn?.destroy();
        this._btn = this._icone = this._label = this._section = null;
    }
}
