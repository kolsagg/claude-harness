# Goals
Done criterion is set by the user. A goal closes when its criterion is met and no open task points at it.

- G1 Başka bir makinede ya da cloud ortamında Claude'a repo linki verilip "bunu kur" denince, kurulum bu makinedeki mevcut harness gibi olur — bitti ölçütü: sahte bir ev dizinine (temiz makine yerine) kurulum çalışır, `doctor.py` yeşil verir; skill'ler, plugin/marketplace listesi, global CLAUDE.md ve ayarlar kaynak makineyle eşleşir (sahibin kaynak cümlesi, 2026-10-06).
- G2 Kuran kişinin kendi bilgileri yazılır: ad, dil, vault yolu, GitHub sahibi sorulur; repoda sahibe ait kişisel bilgi ve yol yoktur — bitti ölçütü: scrub taraması sıfır bulgu verir; kurulum sonrası dosyalarda yer tutucu (`{{...}}`) kalmaz.
- G3 Opsiyonel parçalar soruyla gelir: vault kurulu mu, Orca kullanıyor mu, Codex kullanıyor mu; Claude Code her zaman temeldir — bitti ölçütü: her soru hayır cevabında ilgili parçalar kurulmaz, evet cevabında kurulur (testle gösterilir).
- G4 Beyin'deki gibi güncellenebilir: bu makinede `export.py` + push, diğer makinede "harness'i güncelle" — bitti ölçütü: ikinci kurulum çalıştırması idempotenttir, kullanıcının yerel eklediği ayarları ezmez.
