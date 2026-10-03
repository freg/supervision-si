# -*- coding: utf-8 -*-
"""#658 (item 112) : migration d'un serveur vers la virtualisation -- argv create / import_disk / set / destroy (liste blanche,
confirmation), rattachement du disque importé, image Linux à chaud (validation, disque parent, pipeline dd | zstd)."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from si_agent import vmctl, imagectl

class Migration(unittest.TestCase):
    def test_create(self):
        argv, err = vmctl.build_argv({"vmid": 200, "action": "create", "name": "srv-alpha", "ostype": "win11", "storage": "local-lvm", "link_down": 1, "memory": 8192, "cores": 4})
        self.assertIsNone(err); self.assertEqual(argv[:4], ["qm", "create", "200", "--name"]); self.assertIn("virtio,bridge=vmbr0,link_down=1", argv); self.assertIn("ovmf", argv); self.assertIn("local-lvm:1,version=v2.0", argv)
        argv, err = vmctl.build_argv({"vmid": 201, "action": "create", "kind": "lxc", "name": "ct-alpha", "template": "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst", "storage": "local-lvm", "ip": "192.0.2.10/24", "gateway": "192.0.2.1"})
        self.assertIsNone(err); self.assertEqual(argv[:4], ["pct", "create", "201", "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst"]); self.assertIn("name=eth0,bridge=vmbr0,ip=192.0.2.10/24,gw=192.0.2.1", argv); self.assertIn("--start", argv)
        self.assertEqual(vmctl.build_argv({"vmid": 200, "action": "create"})[1], "name (nom de la VM / du conteneur) requis")
        self.assertEqual(vmctl.build_argv({"vmid": 200, "action": "create", "name": "x", "bridge": "eth0"})[1], "bridge : vmbrN")
        self.assertEqual(vmctl.build_argv({"vmid": 200, "action": "create", "name": "x", "ostype": "win11"})[1], "storage requis pour Windows (disque EFI et TPM)")
        self.assertEqual(vmctl.build_argv({"vmid": 201, "action": "create", "kind": "lxc", "name": "x", "template": "../etc", "storage": "local"})[1][:8], "template")

    def test_import_set_destroy(self):
        self.assertEqual(vmctl.build_argv({"vmid": 200, "action": "import_disk", "path": "/var/lib/vz/import/srv.vhdx", "storage": "local-lvm", "format": "qcow2"}), (["qm", "importdisk", "200", "/var/lib/vz/import/srv.vhdx", "local-lvm", "--format", "qcow2"], None))
        self.assertIn("path", vmctl.build_argv({"vmid": 200, "action": "import_disk", "path": "srv.vhdx; id", "storage": "local-lvm"})[1])
        self.assertEqual(vmctl.build_argv({"vmid": 200, "action": "import_disk", "kind": "lxc", "path": "/x", "storage": "l"})[1], "import_disk : VM qemu seulement")
        self.assertEqual(vmctl.build_argv({"vmid": 200, "action": "set", "options": {"net0": "virtio,bridge=vmbr0", "boot": "order=scsi0"}}), (["qm", "set", "200", "--net0", "virtio,bridge=vmbr0", "--boot", "order=scsi0"], None))
        self.assertIn("refusée", vmctl.build_argv({"vmid": 200, "action": "set", "options": {"args": "-device x"}})[1])
        self.assertIn("invalide", vmctl.build_argv({"vmid": 200, "action": "set", "options": {"name": "a;b"}})[1])
        self.assertEqual(vmctl.build_argv({"vmid": 200, "action": "destroy", "confirm": "200"}), (["qm", "destroy", "200", "--purge", "1", "--destroy-unreferenced-disks", "1"], None))
        self.assertEqual(vmctl.build_argv({"vmid": 200, "action": "destroy", "confirm": "201"})[1], "destroy : confirm doit répéter le vmid (200)")
        self.assertEqual(vmctl.build_argv({"vmid": 201, "kind": "lxc", "action": "destroy", "confirm": 201})[0], ["pct", "destroy", "201", "--purge", "1"])

    def test_attach(self):
        self.assertEqual(vmctl.parse_unused("boot: order=scsi0\nmemory: 2048\nunused0: local-lvm:vm-200-disk-2\n"), "local-lvm:vm-200-disk-2")
        self.assertIsNone(vmctl.parse_unused("memory: 2048\n"))
        self.assertEqual(vmctl.build_attach_argv(200, "scsi0", "local-lvm:vm-200-disk-2"), (["qm", "set", "200", "--scsi0", "local-lvm:vm-200-disk-2,discard=on", "--boot", "order=scsi0"], None))
        self.assertEqual(vmctl.build_attach_argv(200, "sata0", "local:200/vm-200-disk-0.qcow2", boot=False), (["qm", "set", "200", "--sata0", "local:200/vm-200-disk-0.qcow2"], None))
        self.assertIn("introuvable", vmctl.build_attach_argv(200, "scsi0", None)[1]); self.assertIn("attach", vmctl.build_attach_argv(200, "hda", "a:b")[1])

    def test_linux_image(self):
        plan, err = imagectl.validate_linux({"target": "/mnt/images/", "transfer": True})
        self.assertIsNone(err); self.assertEqual(plan["target_dir"], "/mnt/images"); self.assertIsNone(plan["device"]); self.assertTrue(plan["transfer"])
        self.assertIn("target", imagectl.validate_linux({"target": "images"})[1]); self.assertIn("device", imagectl.validate_linux({"target": "/mnt/i", "device": "sda"})[1])
        chain = {"/dev/mapper/vg-root": "sda2\n", "/dev/sda2": "sda\n", "/dev/sda": ""}
        self.assertEqual(imagectl.parent_disk("/dev/mapper/vg-root", lambda d: chain.get(d, "")), "/dev/sda")
        self.assertEqual(imagectl.parent_disk("/dev/nvme0n1p2", lambda d: {"/dev/nvme0n1p2": "nvme0n1"}.get(d, "")), "/dev/nvme0n1")
        self.assertEqual(imagectl.parent_disk("", lambda d: ""), None)
        self.assertEqual(imagectl.build_linux_argv("/dev/sda", "/mnt/images/srv-20261003-1000.img.zst"), ["sh", "-c", "dd if=/dev/sda bs=4M status=none | zstd -T0 -3 -q -o /mnt/images/srv-20261003-1000.img.zst"])
        self.assertTrue(imagectl.target_file(plan, "srv-alpha", ext="img.zst").endswith(".img.zst"))

if __name__ == "__main__":
    unittest.main()
