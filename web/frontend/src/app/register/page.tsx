"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { register } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register(email, password, name);
      router.push("/search");
    } catch (err: any) {
      setError(err.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="text-2xl font-bold text-brand-700">
            Autofare
          </Link>
        </div>
        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-xl shadow-lg border p-8"
        >
          <h2 className="text-2xl font-bold mb-6">Create your account</h2>
          <p className="text-gray-600 mb-6">
            Get 2 free searches per month. No credit card required.
          </p>

          {error && (
            <div className="bg-red-50 text-red-700 p-3 rounded-lg mb-4 text-sm">
              {error}
            </div>
          )}

          <label className="block mb-4">
            <span className="text-sm font-medium text-gray-700">Name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-brand-500 focus:ring-brand-500"
            />
          </label>

          <label className="block mb-4">
            <span className="text-sm font-medium text-gray-700">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-brand-500 focus:ring-brand-500"
              required
            />
          </label>

          <label className="block mb-6">
            <span className="text-sm font-medium text-gray-700">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-brand-500 focus:ring-brand-500"
              required
              minLength={8}
            />
          </label>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-brand-600 text-white py-2 rounded-lg hover:bg-brand-700 transition disabled:opacity-50"
          >
            {loading ? "Creating account..." : "Create Account"}
          </button>

          <p className="mt-4 text-center text-sm text-gray-600">
            Already have an account?{" "}
            <Link href="/login" className="text-brand-600 hover:underline">
              Log in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
