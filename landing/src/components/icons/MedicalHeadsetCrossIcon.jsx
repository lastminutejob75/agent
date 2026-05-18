/**
 * Symbole casque + croix médicale fourni dans la maquette.
 * Traits epais, coins arrondis, micro raccorde a l'oreillette droite.
 */
export default function MedicalHeadsetCrossIcon({
  size = 38,
  className = "",
  ariaHidden = true,
}) {
  return (
    <svg
      viewBox="0 0 128 128"
      width={size}
      height={size}
      className={className}
      aria-hidden={ariaHidden}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
        <path
          d="M34 56C34 33.4 47.4 22 64 22s30 11.4 30 34"
          strokeWidth="7.5"
        />
        <rect x="21" y="57" width="20" height="42" rx="10" strokeWidth="7.5" />
        <rect x="87" y="57" width="20" height="42" rx="10" strokeWidth="7.5" />
        <path
          d="M97 99c-1.2 15.2-12.6 23-29 23h-8"
          strokeWidth="7.5"
        />
        <rect x="42" y="114" width="27" height="14" rx="7" strokeWidth="7.5" />
        <path
          d="M61 60h6c1.7 0 3 1.3 3 3v6h6c1.7 0 3 1.3 3 3v5c0 1.7-1.3 3-3 3h-6v6c0 1.7-1.3 3-3 3h-6c-1.7 0-3-1.3-3-3v-6h-6c-1.7 0-3-1.3-3-3v-5c0-1.7 1.3-3 3-3h6v-6c0-1.7 1.3-3 3-3Z"
          strokeWidth="4.6"
        />
      </g>
    </svg>
  );
}
