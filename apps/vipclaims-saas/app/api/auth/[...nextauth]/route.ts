"use server";

import NextAuth from "next-auth/next";
import GoogleProvider from "next-auth/providers/google";

// Keep untyped to work across next-auth v4/v5 type changes while we pin the runtime.
const authOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
    }),
  ],
  session: {
    strategy: "jwt",
  },
  callbacks: {
    // Use broad types to stay compatible across next-auth versions in Render.
    async session({ session, token }: { session: any; token: any }) {
      if (session.user && token.sub) {
        session.user.id = token.sub;
      }
      return session;
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
};

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };

