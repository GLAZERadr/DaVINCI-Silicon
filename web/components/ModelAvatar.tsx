// Avatar for whoever wrote a piece of AI text. Muse Spark gets the Muse
// character; any other model (the offline stand-in, a replay of one) keeps a
// plain "AI" mark, so the picture never claims a model that did not answer.
export default function ModelAvatar({ model, size = 22 }: { model?: string; size?: number }) {
  const muse = /muse/i.test(model ?? "");
  return muse ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img className="model-avatar" src="/brand/muse-avatar.png" alt="Muse Spark" width={size} height={size} />
  ) : (
    <span className="model-avatar model-avatar-ai" style={{ width: size, height: size }} aria-hidden="true">AI</span>
  );
}
