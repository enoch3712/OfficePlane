import React, {type ReactNode} from 'react';
import Content from '@theme-original/DocItem/Content';
import type ContentType from '@theme/DocItem/Content';
import type {WrapperProps} from '@docusaurus/types';
import {useDoc} from '@docusaurus/plugin-content-docs/client';
import AskAI from '@site/src/components/AskAI';

type Props = WrapperProps<typeof ContentType>;

export default function ContentWrapper(props: Props): ReactNode {
  const {metadata} = useDoc();
  return (
    <>
      <AskAI title={metadata.title} />
      <Content {...props} />
    </>
  );
}
