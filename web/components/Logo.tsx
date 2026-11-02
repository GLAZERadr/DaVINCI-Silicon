// Official DaVINCI mark (web/public/brand/davinci-mark.png, from Adrian's logo
// file, 1 Nov). The wordmark is live text so it follows light and dark mode;
// "Silicon" is the DaVINCI series for chip-design acceleration.
export function Mark({ height = 24 }: { height?: number }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src="/brand/davinci-mark.png" alt="" width={Math.round(height * 440 / 242)} height={height} />
  );
}

export default function Logo() {
  return (
    <>
      <Mark />
      <span className="word">DaVINCI <span className="word-series">Silicon</span></span>
    </>
  );
}
