'use server';
import { AuthWrapperContext, withUserAuth } from '@/lib/auth-wrapper';
import { maskDataForLlmApiKey } from '@/lib/maskdata';
import { prisma } from '@/lib/prisma';
import { encryptWithPublicKey, decryptWithPrivateKey } from '@/lib/crypto';
import fs from 'fs';
import path from 'path';

const publicKey = fs.readFileSync(path.join(process.cwd(), 'keys', 'public.pem'), 'utf8');
const privateKey = fs.readFileSync(path.join(process.cwd(), 'keys', 'private.pem'), 'utf8');

export const getLlmConfig = withUserAuth(async ({ organization }: AuthWrapperContext<{}>) => {
  const config = await prisma.llmConfigs.findFirst({
    where: { organizationId: organization.id, type: 'default' },
  });

  if (!config) return null;

  const decryptedApiKey = config.apiKey ? decryptWithPrivateKey(config.apiKey, privateKey) : '';

  return {
    ...config,
    apiKey: decryptedApiKey ? maskDataForLlmApiKey(decryptedApiKey) : '',
    baseUrl: config.baseUrl ? config.baseUrl.replace(/\/\/[^:]+:[^@]+@/, '//***:***@') : '',
  };
});

export const updateLlmConfig = withUserAuth(
  async ({
    organization,
    args,
  }: AuthWrapperContext<{
    model: string;
    apiKey: string;
    baseUrl: string;
    maxTokens: number;
    temperature: number;
    apiType: string;
  }>) => {
    const encryptedApiKey = args.apiKey ? encryptWithPublicKey(args.apiKey, publicKey) : '';

    const existingConfig = await prisma.llmConfigs.findFirst({
      where: { organizationId: organization.id, type: 'default' },
    });

    if (!existingConfig) {
      await prisma.llmConfigs.create({
        data: {
          organizationId: organization.id,
          apiKey: encryptedApiKey,
          baseUrl: args.baseUrl,
          model: args.model,
          maxTokens: args.maxTokens,
          temperature: args.temperature,
          apiType: args.apiType,
          isActive: true,
          type: 'default',
        },
      });
    } else {
      await prisma.llmConfigs.update({
        where: { id: existingConfig.id, organizationId: organization.id },
        data: {
          apiKey: encryptedApiKey,
          baseUrl: args.baseUrl,
          model: args.model,
          maxTokens: args.maxTokens,
          temperature: args.temperature,
          apiType: args.apiType,
          isActive: true,
        },
      });
    }
  }
);
