#!/usr/bin/env bash
# Siyah zeminli filigran MP4'ünden şeffaf ProRes 4444 MOV üretir.
# İçerik siyah üstünde parlak gümüş olduğu için alfa = en parlak kanal; renk alfaya bölünür
# (unpremultiply), böylece siyah üstüne konunca orijinalle aynı, başka zeminde temiz görünür.
# Kullanım: bash alpha.sh <girdi.mp4> <çıktı.mov>
set -euo pipefail
in="$1"; out="$2"
M='max(r(X,Y),max(g(X,Y),b(X,Y)))'
A="if(lt($M,4),0,$M)"
ffmpeg -y -loglevel error -i "$in" -an -vf "format=rgba,geq=r='min(255,r(X,Y)*255/max($M,1))':g='min(255,g(X,Y)*255/max($M,1))':b='min(255,b(X,Y)*255/max($M,1))':a='$A'" \
  -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le -alpha_bits 16 -vendor apl0 "$out"
echo "alpha ok: $out"
