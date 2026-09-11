-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 9.4.1                                       //
-- // Date : 2021-12-21                                     //
-- ///////////////////////////////////////////////////////////

UPDATE `${prefix}parameter` 
SET parameterValue='You are approver of element <a href="${url}" > ${item} #${id}</a> : "${name}".<br/>Please access <a href="${url}" >this element</a> and follow approval process.'
WHERE parameterCode='paramMailBodyApprover' and parameterValue='[${dbName}] You are approver of <a href="${url}" > Document #${id}</a> : "${name}".<br/>Please access <a href="${url}" >this document</a> and follow approval process.';
UPDATE `${prefix}parameter` SET parameterValue='[${dbName}] Message from ${sender} : You need to approve an element' 
WHERE parameterCode='paramMailTitleApprover' and parameterValue='[${dbName}] message from ${sender} : You need to approve a document';

UPDATE `${prefix}menu` SET level='ReadWriteTool' WHERE id=185;
UPDATE `${prefix}menu` SET level='ReadWriteType' WHERE id in (190, 193, 202);

UPDATE `${prefix}accessright` SET idAccessProfile=1000001 where idAccessProfile=8 and idMenu in (185, 190, 193, 202, 268, 269, 272, 273);
UPDATE `${prefix}accessright` SET idAccessProfile=1000003 where idAccessProfile=3 and idMenu in (185, 190, 193, 202, 268, 269, 272, 273);
UPDATE `${prefix}accessright` SET idAccessProfile=1000002 where idAccessProfile=2 and idMenu in (185, 190, 193, 202, 268, 269, 272, 273);
UPDATE `${prefix}accessright` SET idAccessProfile=1000001 where idAccessProfile=7 and idMenu in (185, 190, 193, 202, 268, 269, 272, 273);
