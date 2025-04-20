import 'package:flutter/material.dart';

class MenuListTile extends StatelessWidget {
  final String title;
  final IconData icon;
  final Color iconColor;
  final bool enabled;
  final VoidCallback? onTap;

  const MenuListTile({
    super.key,
    required this.title,
    required this.icon,
    required this.iconColor,
    this.enabled = true,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      tileColor:
          iconColor == Colors.orangeAccent
              ? const Color.fromARGB(255, 255, 247, 234)
              : const Color.fromARGB(255, 249, 245, 255),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      enabled: enabled,
      leading: Icon(icon, color: iconColor),
      title: Text(
        title.isEmpty ? 'Menu non disponibile' : title,
        style: const TextStyle(fontWeight: FontWeight.bold),
      ),
      trailing: const Icon(Icons.chevron_right),
      onTap: enabled ? onTap : null,
    );
  }
}
