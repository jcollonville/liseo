# Third-party sources

`updfparser/` is uPDFParser commit `6060d123441a06df699eb275ae5ffdd50409b8f3`
(LGPL-3.0-or-later, Grégory Soutadé). The official forge
(`forge.soutade.fr`) answers git clones with HTTP 402, so this copy comes from
the public mirror `https://git.mopalinski.com/soutade/uPDFParser`, the same
commit the forge page shows as current (`Add removeObject() method`).

libgourou itself is not vendored. The image clones
`https://github.com/rledisez/libgourou` at `906b8a37334ac5d37dcae24c7508a427c19dbb66`
(v0.8.10) and applies `patches/libgourou-no-drm-removal.patch` before compiling.
That keeps the DRM-removal utility out of this repository and out of the image.
